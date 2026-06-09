"""Seed 8 catalog markets (Loop L)

Revision ID: 015_seed_catalog_markets
Revises: 014_paper_order_outcome
Create Date: 2026-06-09
"""

from typing import Sequence, Union

from alembic import op

revision: str = "015_seed_catalog_markets"
down_revision: Union[str, None] = "014_paper_order_outcome"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# lock_at values aligned with app.services.market_service seed_catalog_markets
_CATALOG_LOCK = "2026-07-15 19:30:00+00"
_WC_LOCK = "2026-06-11 21:00:00+00"

_MARKETS_SQL = """
INSERT INTO markets (
    id,
    slug,
    title,
    question,
    category,
    icon,
    volume,
    traders,
    market_count,
    description,
    resolution,
    status,
    lock_at
) VALUES
(
    gen_random_uuid(),
    'nba-2025-01-15-lal-bos',
    'Lakers vs Celtics',
    'Will the Lakers win?',
    'NBA',
    '🏀',
    2413000,
    3214,
    3,
    'Head-to-head paper market on the Lakers vs Celtics matchup.',
    'Resolves YES if the Lakers win the game, otherwise NO.',
    'open',
    '{catalog_lock}'::timestamptz
),
(
    gen_random_uuid(),
    'elect-la-mayor-2026',
    'Los Angeles mayoral election',
    'Will the incumbent win re-election?',
    'Elections',
    '🗳️',
    842000,
    1104,
    1,
    'Paper market on the certified Los Angeles mayoral result.',
    'Resolves to the certified winner of the election.',
    'open',
    '{catalog_lock}'::timestamptz
),
(
    gen_random_uuid(),
    'wc2026-m1-mex-homewin',
    'WC2026 M1: Will Mexico win vs South Africa?',
    'Will Mexico win their Group A opener vs South Africa?',
    'FIFA WC2026',
    '⚽',
    0,
    0,
    3,
    'FIFA World Cup 2026 Group A, Match 1: Mexico vs South Africa (regulation).',
    'Resolves YES if Mexico win in regulation. Paper-trading simulation only.',
    'open',
    '{wc_lock}'::timestamptz
),
(
    gen_random_uuid(),
    'wc2026-m1-draw',
    'WC2026 M1: Will Mexico vs South Africa draw?',
    'Will Mexico vs South Africa end in a draw?',
    'FIFA WC2026',
    '⚽',
    0,
    0,
    3,
    'FIFA World Cup 2026 Group A, Match 1: Mexico vs South Africa (regulation).',
    'Resolves YES if the match ends in a draw. Paper-trading simulation only.',
    'open',
    '{wc_lock}'::timestamptz
),
(
    gen_random_uuid(),
    'wc2026-m1-rsa-awaywin',
    'WC2026 M1: Will South Africa win vs Mexico?',
    'Will South Africa win their Group A opener vs Mexico?',
    'FIFA WC2026',
    '⚽',
    0,
    0,
    3,
    'FIFA World Cup 2026 Group A, Match 1: Mexico vs South Africa (regulation).',
    'Resolves YES if South Africa win in regulation. Paper-trading simulation only.',
    'open',
    '{wc_lock}'::timestamptz
),
(
    gen_random_uuid(),
    'wc2026-winner-brazil',
    'WC2026: Will Brazil win the World Cup?',
    'Will Brazil win the FIFA World Cup 2026?',
    'FIFA WC2026',
    '⚽',
    0,
    0,
    1,
    'Brazil tournament-winner market for FIFA World Cup 2026.',
    'Resolves YES if Brazil lift the trophy. Paper-trading simulation only.',
    'open',
    '{wc_lock}'::timestamptz
),
(
    gen_random_uuid(),
    'wc2026-winner-france',
    'WC2026: Will France win the World Cup?',
    'Will France win the FIFA World Cup 2026?',
    'FIFA WC2026',
    '⚽',
    0,
    0,
    1,
    'France tournament-winner market for FIFA World Cup 2026.',
    'Resolves YES if France lift the trophy. Paper-trading simulation only.',
    'open',
    '{wc_lock}'::timestamptz
),
(
    gen_random_uuid(),
    'wc2026-winner-argentina',
    'WC2026: Will Argentina win the World Cup?',
    'Will Argentina win the FIFA World Cup 2026?',
    'FIFA WC2026',
    '⚽',
    0,
    0,
    1,
    'Argentina tournament-winner market for FIFA World Cup 2026.',
    'Resolves YES if Argentina lift the trophy. Paper-trading simulation only.',
    'open',
    '{wc_lock}'::timestamptz
)
ON CONFLICT (slug) DO NOTHING
"""


def upgrade() -> None:
    op.execute(
        _MARKETS_SQL.format(catalog_lock=_CATALOG_LOCK, wc_lock=_WC_LOCK)
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM markets
        WHERE slug IN (
            'nba-2025-01-15-lal-bos',
            'elect-la-mayor-2026',
            'wc2026-m1-mex-homewin',
            'wc2026-m1-draw',
            'wc2026-m1-rsa-awaywin',
            'wc2026-winner-brazil',
            'wc2026-winner-france',
            'wc2026-winner-argentina'
        )
        """
    )
