"""partial unique index: one active booking per user

Revision ID: 0005_one_active_booking
Revises: 0004_booking_progress
Create Date: 2026-06-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_one_active_booking"
down_revision: Union[str, None] = "0004_booking_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 数据库层兜底"每用户最多一个进行中任务"，防止 has_active 的 TOCTOU 竞态。
    op.create_index(
        "uq_booking_one_active_per_user",
        "booking",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_booking_one_active_per_user", table_name="booking")
