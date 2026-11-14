"""user.exclude_from_stats: keep test accounts out of the admin stats

Revision ID: 0011_user_exclude_from_stats
Revises: 0010_route_pack_opens
Create Date: 2026-11-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_user_exclude_from_stats"
down_revision: Union[str, None] = "0010_route_pack_opens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("exclude_from_stats", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user", "exclude_from_stats")
