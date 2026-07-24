from pathlib import Path


def test_alpha_validation_migration_chains_on_wave_104_head():
    source = Path("alembic/versions/066_alpha_validation.py").read_text(
        encoding="utf-8"
    )

    assert 'revision: str = "066_alpha_validation"' in source
    assert len("066_alpha_validation") <= 32
    assert (
        'down_revision: Union[str, Sequence[str], None] = "065_social_community"'
        in source
    )
    assert '"alpha_factor_snapshots"' in source
    assert '"alpha_closing_lines"' in source
