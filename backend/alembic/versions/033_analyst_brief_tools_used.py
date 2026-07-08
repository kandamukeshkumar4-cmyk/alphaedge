"""persist market tools used on analyst briefs

Revision ID: 033_analyst_brief_tools_used
Revises: 032_agent_memories
Create Date: 2026-07-08
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033_analyst_brief_tools_used"
down_revision: Union[str, Sequence[str], None] = "032_agent_memories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analyst_briefs", sa.Column("tools_used", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyst_briefs", "tools_used")
