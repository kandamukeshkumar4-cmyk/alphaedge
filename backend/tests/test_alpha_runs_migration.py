from pathlib import Path


def test_alpha_runs_migration_has_the_current_single_chain_head_and_short_revision():
    source = Path("alembic/versions/064_alpha_runs.py").read_text(encoding="utf-8")

    assert 'revision: str = "064_alpha_runs"' in source
    assert len("064_alpha_runs") <= 32
    assert 'down_revision: Union[str, Sequence[str], None] = "063_marketplace_ratings"' in source
    assert '"alpha_runs"' in source
