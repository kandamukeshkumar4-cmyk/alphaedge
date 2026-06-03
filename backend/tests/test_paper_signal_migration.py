from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_paper_signals_use_incremental_migration():
    migration = (
        ROOT / "alembic" / "versions" / "003_paper_signals.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: Union[str, None] = "002"' in migration
    assert 'op.create_table(\n        "paper_signals",' in migration
    assert '"market_id"' in migration
    assert '"account_id"' in migration
    assert '"outcome"' in migration
    assert "ix_paper_signals_account_market" in migration
    assert "unique=True" in migration
