"""route pack open log (redirect links)

Revision ID: 0010_route_pack_opens
Revises: 0009_route_packs
Create Date: 2026-11-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_route_pack_opens"
down_revision: Union[str, None] = "0009_route_packs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "route_pack_open",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("pack_slug", sa.String(64), nullable=False),
        sa.Column("route_index", sa.Integer(), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("redirected_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_route_pack_open_user_id", "route_pack_open", ["user_id"])
    op.create_index("ix_route_pack_open_pack_slug", "route_pack_open", ["pack_slug"])
    op.create_index("ix_route_pack_open_created_at", "route_pack_open", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_route_pack_open_created_at", table_name="route_pack_open")
    op.drop_index("ix_route_pack_open_pack_slug", table_name="route_pack_open")
    op.drop_index("ix_route_pack_open_user_id", table_name="route_pack_open")
    op.drop_table("route_pack_open")
