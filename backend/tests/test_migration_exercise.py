"""Loop111: migration exercise + model/DDL parity harness.

Why this exists
---------------
The normal test suite builds its schema with ``Base.metadata.create_all``
(see ``tests/conftest.py``), which means **no alembic migration has ever been
executed by CI**. Drift between ``app/db/models.py`` and the migration DDL has
twice been closed by hand (revisions 065 / 066). This module closes the gap
automatically:

1. ``test_migration_upgrade_downgrade_upgrade`` — against a throwaway scratch
   database: ``upgrade head`` -> ``downgrade base`` -> ``upgrade head``.
2. ``test_model_ddl_parity`` — after ``upgrade head``, reflect the real schema
   and diff it against ``Base.metadata``. Any missing/extra table, missing/extra
   column, type mismatch, nullability mismatch, or unique-constraint mismatch
   is reported in a readable difference table.

   The repo already carries a large amount of *pre-existing* drift (revision
   001 created most columns without ``nullable=False`` even though the models
   declare it). Fixing that needs new migrations, which is out of this
   harness's scope, so the parity check is a **ratchet**: the known drift is
   frozen in ``tests/migration_parity_baseline.json`` and the test fails only
   on drift that is *not* in the baseline — i.e. on the next 065/066-style
   table/column that a migration forgets. Regenerate the baseline with
   ``UPDATE_MIGRATION_PARITY_BASELINE=1`` after a migration deliberately
   changes the picture, and shrink it whenever drift is genuinely fixed
   (stale entries are reported, but do not fail the run).

Environment honesty
-------------------
The migrations are **PostgreSQL-only** (``CREATE TYPE ... AS ENUM``,
``ALTER TYPE ... ADD VALUE``, ``JSONB``, ``postgresql.UUID``, ``now()``
server defaults). SQLite — what the rest of the suite uses — cannot execute
them, so there is no honest portable fallback. This module therefore requires
a PostgreSQL DSN in ``TEST_MIGRATION_DATABASE_URL`` and skips loudly when it is
absent. No new dependencies are introduced: ``psycopg2-binary`` is already a
first-class runtime dependency.

Safety
------
* The DSN is only ever used as an *admin* connection; the exercise runs inside
  a freshly ``CREATE DATABASE``-d scratch database (``alphaedge_migtest_*``)
  that is dropped afterwards. The database named in the DSN is never migrated.
* Non-local hosts are refused unless ``TEST_MIGRATION_ALLOW_REMOTE_SCRATCH=1``
  is set explicitly, so a stray production DSN cannot be exercised by accident.
* No DSN, password, or other credential is ever printed: only the sanitized
  ``host:port`` and the scratch database name appear in output.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine

from app.db import models  # noqa: F401  (registers all tables on Base.metadata)
from app.db.base import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]
ADMIN_DSN = os.getenv("TEST_MIGRATION_DATABASE_URL", "").strip()
ALLOW_REMOTE = os.getenv("TEST_MIGRATION_ALLOW_REMOTE_SCRATCH") == "1"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "", None}

SKIP_REASON = (
    "MIGRATION EXERCISE SKIPPED: no TEST_MIGRATION_DATABASE_URL set. "
    "The alembic migrations are PostgreSQL-only (CREATE TYPE ... AS ENUM, "
    "JSONB, postgresql.UUID), so they cannot run on the suite's default "
    "sqlite+aiosqlite engine. Export a PostgreSQL admin DSN to enable this "
    "harness, e.g. "
    "TEST_MIGRATION_DATABASE_URL=postgresql://<user>:<pw>@localhost:5432/postgres"
)

# NOTE: the skip lives in the ``scratch_dsn`` fixture rather than at module
# level so the pure-logic detector test below still runs everywhere.


# --------------------------------------------------------------------------- #
# scratch database plumbing
# --------------------------------------------------------------------------- #


def _sanitized(dsn: str) -> str:
    """host:port/dbname with all credentials stripped — safe to print."""
    parts = urlsplit(dsn)
    host = parts.hostname or "?"
    port = parts.port or 5432
    return f"{host}:{port}{parts.path}"


def _with_database(dsn: str, dbname: str) -> str:
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", "", ""))


def _assert_scratch_safe(dsn: str) -> None:
    parts = urlsplit(dsn)
    if not parts.scheme.startswith("postgres"):
        pytest.fail(
            "TEST_MIGRATION_DATABASE_URL must be a PostgreSQL DSN "
            f"(got scheme {parts.scheme!r})"
        )
    if parts.hostname not in LOCAL_HOSTS and not ALLOW_REMOTE:
        pytest.fail(
            "Refusing to use a non-local database host for the migration "
            f"exercise ({_sanitized(dsn)}). This harness creates and drops "
            "databases; point it at a local/scratch PostgreSQL, or set "
            "TEST_MIGRATION_ALLOW_REMOTE_SCRATCH=1 if the host really is a "
            "disposable CI service."
        )


@pytest.fixture(scope="module")
def scratch_dsn() -> str:
    """Create a throwaway database, yield its DSN, drop it afterwards."""
    if not ADMIN_DSN:
        pytest.skip(SKIP_REASON)
    _assert_scratch_safe(ADMIN_DSN)
    dbname = f"alphaedge_migtest_{uuid.uuid4().hex[:12]}"
    admin = create_engine(ADMIN_DSN, isolation_level="AUTOCOMMIT", future=True)
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{dbname}"'))
    except Exception as exc:  # pragma: no cover - infra failure path
        admin.dispose()
        pytest.skip(
            "MIGRATION EXERCISE SKIPPED: could not create a scratch database on "
            f"{_sanitized(ADMIN_DSN)} ({type(exc).__name__}). The DSN must have "
            "CREATEDB rights."
        )
    print(f"\n[loop111] scratch database created: {dbname} on {_sanitized(ADMIN_DSN)}")
    try:
        yield _with_database(ADMIN_DSN, dbname)
    finally:
        with admin.connect() as conn:
            conn.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :d AND pid <> pg_backend_pid()"
                ),
                {"d": dbname},
            )
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{dbname}"'))
        admin.dispose()


def _alembic_config(dsn: str):
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", dsn)
    # alembic/env.py prefers this override over settings.database_url_sync.
    os.environ["ALEMBIC_DATABASE_URL_SYNC"] = dsn
    return cfg


@pytest.fixture(scope="module")
def migrated_dsn(scratch_dsn: str) -> str:
    """Scratch DB at ``head`` after a full upgrade/downgrade/upgrade cycle."""
    from alembic import command

    previous = os.environ.get("ALEMBIC_DATABASE_URL_SYNC")
    cfg = _alembic_config(scratch_dsn)
    try:
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        yield scratch_dsn
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_DATABASE_URL_SYNC", None)
        else:
            os.environ["ALEMBIC_DATABASE_URL_SYNC"] = previous


# --------------------------------------------------------------------------- #
# 1. migration exercise
# --------------------------------------------------------------------------- #


def test_migration_upgrade_downgrade_upgrade(migrated_dsn: str) -> None:
    """upgrade head -> downgrade base -> upgrade head must all succeed.

    The fixture performs the cycle; here we assert the end state is really at
    the single head revision and that the schema is non-empty.
    """
    from alembic.script import ScriptDirectory

    cfg = _alembic_config(migrated_dsn)
    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())
    assert len(heads) == 1, f"expected a single alembic head, got {sorted(heads)}"

    engine = create_engine(migrated_dsn, future=True)
    try:
        with engine.connect() as conn:
            db_rev = set(
                r[0] for r in conn.execute(sa.text("SELECT version_num FROM alembic_version"))
            )
            tables = set(sa.inspect(conn).get_table_names())
    finally:
        engine.dispose()

    assert db_rev == heads, f"database at {sorted(db_rev)}, alembic head {sorted(heads)}"
    assert len(tables) > 1, "upgrade head produced no application tables"


# --------------------------------------------------------------------------- #
# 2. model / DDL parity
# --------------------------------------------------------------------------- #

# Diff kinds we hold the migrations to. server_default / index-name churn is
# deliberately excluded: it is noisy and not a correctness risk, unlike a
# missing table, column, type, nullability or unique constraint.
TRACKED_KINDS = {
    "add_table",
    "remove_table",
    "add_column",
    "remove_column",
    "modify_type",
    "modify_nullable",
    "add_constraint",
    "remove_constraint",
}


def _describe(diff) -> tuple[str, str, str] | None:
    """Normalize one alembic autogenerate diff entry into a printable row.

    Returns ``(kind, object, detail)`` or ``None`` when the entry is not one of
    the tracked (correctness-relevant) kinds.

    Direction note: alembic compares *database -> metadata*, so ``add_table``
    means "the models define it but the migrations never created it" (the
    065/066 failure mode), and ``remove_table`` means the migrations created
    something the models no longer declare.
    """
    kind = diff[0]
    if kind == "add_table":
        return ("MISSING TABLE (in models, not in migrations)", diff[1].name, "")
    if kind == "remove_table":
        return ("EXTRA TABLE (in migrations, not in models)", diff[1].name, "")
    if kind == "add_column":
        col = diff[3]
        return (
            "MISSING COLUMN (in models, not in migrations)",
            f"{diff[2]}.{col.name}",
            f"{col.type}",
        )
    if kind == "remove_column":
        col = diff[3]
        return (
            "EXTRA COLUMN (in migrations, not in models)",
            f"{diff[2]}.{col.name}",
            f"{col.type}",
        )
    if kind in {"add_constraint", "remove_constraint"}:
        obj = diff[1]
        if not isinstance(obj, sa.UniqueConstraint):
            return None
        table = obj.table.name if obj.table is not None else "?"
        cols = ",".join(c.name for c in obj.columns)
        label = (
            "MISSING UNIQUE CONSTRAINT (in models, not in migrations)"
            if kind == "add_constraint"
            else "EXTRA UNIQUE CONSTRAINT (in migrations, not in models)"
        )
        return (label, f"{table}({cols})", obj.name or "<unnamed>")
    if isinstance(diff, list):  # modify_* entries arrive wrapped in a list
        return None
    return None


def _describe_modify(diff) -> tuple[str, str, str] | None:
    kind, _schema, table, column, _opts, old, new = diff
    if kind == "modify_nullable":
        return ("NULLABILITY MISMATCH", f"{table}.{column}", f"db={old} models={new}")
    if kind == "modify_type":
        return ("TYPE MISMATCH", f"{table}.{column}", f"db={old} models={new}")
    return None


def _flatten(diffs) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for diff in diffs:
        if isinstance(diff, list):
            for sub in diff:
                if sub[0] in TRACKED_KINDS:
                    row = _describe_modify(sub)
                    if row:
                        rows.append(row)
            continue
        if diff[0] not in TRACKED_KINDS:
            continue
        row = _describe(diff)
        if row:
            rows.append(row)
    return rows


BASELINE_PATH = Path(__file__).with_name("migration_parity_baseline.json")
BASELINE_README = (
    "Known, pre-existing model/DDL drift as of loop111. Generated by "
    "tests/test_migration_exercise.py with UPDATE_MIGRATION_PARITY_BASELINE=1. "
    "Entries are 'DRIFT | OBJECT | DETAIL'. Most of this is revision 001 "
    "creating columns without nullable=False while app/db/models.py declares "
    "it; fixing that requires new migrations. Shrink this list when drift is "
    "fixed - never grow it to silence a new mismatch."
)


def _key(row: tuple[str, str, str]) -> str:
    return " | ".join(row).rstrip(" |").strip()


def _load_baseline() -> set[str]:
    if not BASELINE_PATH.exists():
        return set()
    return set(json.loads(BASELINE_PATH.read_text(encoding="utf-8"))["known_drift"])


def _render(rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return "(no drift)"
    headers = ("DRIFT", "OBJECT", "DETAIL")
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(3)
    ]
    line = "  ".join("-" * w for w in widths)
    out = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)), line]
    for r in sorted(rows):
        out.append("  ".join(r[i].ljust(widths[i]) for i in range(3)))
    return "\n".join(out)


def test_model_ddl_parity(migrated_dsn: str) -> None:
    """The migrated schema must match ``Base.metadata`` — no drift.

    This is the check that would have caught the 065 / 066 hand-diffs.
    """
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    engine = create_engine(migrated_dsn, future=True)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn,
                opts={
                    "compare_type": True,
                    "compare_server_default": False,
                    "include_object": lambda obj, name, type_, reflected, compare_to: (
                        name != "alembic_version"
                    ),
                },
            )
            diffs = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()

    rows = _flatten(diffs)
    keyed = {_key(r): r for r in rows}

    if os.getenv("UPDATE_MIGRATION_PARITY_BASELINE") == "1":  # pragma: no cover
        BASELINE_PATH.write_text(
            json.dumps(
                {"_readme": BASELINE_README, "known_drift": sorted(keyed)},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        pytest.skip(f"baseline regenerated with {len(keyed)} known-drift entries")

    baseline = _load_baseline()
    new = [keyed[k] for k in sorted(set(keyed) - baseline)]
    stale = sorted(baseline - set(keyed))
    if stale:
        print(
            f"\n[loop111] {len(stale)} baseline drift entries are now FIXED; "
            "shrink tests/migration_parity_baseline.json:\n  " + "\n  ".join(stale)
        )
    print(
        f"[loop111] model/DDL parity: {len(keyed)} total drift entries, "
        f"{len(baseline)} baselined, {len(new)} new"
    )

    assert not new, (
        "NEW MODEL/DDL DRIFT: the alembic migrations and app.db.models disagree "
        "in a way that is not in the recorded baseline.\n"
        "(alembic compares database -> models; 'MISSING' = models declare it, "
        "migrations never created it — the 065/066 failure mode.)\n\n"
        + _render(new)
    )


# --------------------------------------------------------------------------- #
# 3. detector self-test (runs everywhere, no database needed)
# --------------------------------------------------------------------------- #


def test_drift_detector_flags_missing_tables_and_columns() -> None:
    """The 065/066 failure mode must survive the flatten/ratchet layer.

    Guards the reporting logic itself: without this, a bug in ``_flatten``
    could make the parity test silently green on real drift. Uses synthetic
    alembic-shaped diffs, so it runs even when no PostgreSQL DSN is available.
    """
    meta = sa.MetaData()
    missing_tbl = sa.Table("brand_new_feature", meta, sa.Column("id", sa.Integer()))
    missing_col = sa.Column("forgotten_flag", sa.Boolean(), nullable=False)

    diffs = [
        ("add_table", missing_tbl),
        ("add_column", None, "markets", missing_col),
        [("modify_nullable", None, "orders", "quantity", {}, True, False)],
        ("add_index", sa.Index("ix_noise", missing_tbl.c.id)),  # untracked noise
    ]
    rows = _flatten(diffs)
    kinds = {r[0] for r in rows}
    objects = {r[1] for r in rows}

    assert any(k.startswith("MISSING TABLE") for k in kinds)
    assert any(k.startswith("MISSING COLUMN") for k in kinds)
    assert "NULLABILITY MISMATCH" in kinds
    assert objects == {"brand_new_feature", "markets.forgotten_flag", "orders.quantity"}
    assert len(rows) == 3, "index churn must not be reported as drift"

    # A brand-new table is not in the recorded baseline, so it would fail the
    # ratchet rather than be absorbed by it.
    assert _key(rows[0]) not in _load_baseline()
    assert "brand_new_feature" in _render(rows)
