"""multiuser profile: user 档案字段重构 + booking 简化

Revision ID: 0002_multiuser_profile
Revises: 0001_initial
Create Date: 2026-06-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_multiuser_profile"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("user", "preferred_pos")
    op.drop_column("user", "time_windows")
    op.drop_column("user", "max_wait_days")
    op.add_column("user", sa.Column("exam_class", sa.String(10)))
    op.add_column("user", sa.Column("pos_ids", sa.JSON()))
    op.add_column("user", sa.Column("expect_after_date", sa.Date()))
    op.add_column("user", sa.Column("expect_before_date", sa.Date()))
    op.add_column("user", sa.Column("expect_time_range", sa.String(20)))
    op.add_column("user", sa.Column("pref_days_of_week", sa.JSON()))
    op.add_column("user", sa.Column("pref_parts_of_day", sa.JSON()))
    op.drop_column("booking", "target_date")
    op.drop_column("booking", "time_window")
    op.drop_column("booking", "pos_code")


def downgrade() -> None:
    op.add_column("booking", sa.Column("pos_code", sa.String(50)))
    op.add_column("booking", sa.Column("time_window", sa.JSON()))
    op.add_column("booking", sa.Column("target_date", sa.Date()))
    op.drop_column("user", "pref_parts_of_day")
    op.drop_column("user", "pref_days_of_week")
    op.drop_column("user", "expect_time_range")
    op.drop_column("user", "expect_before_date")
    op.drop_column("user", "expect_after_date")
    op.drop_column("user", "pos_ids")
    op.drop_column("user", "exam_class")
    op.add_column("user", sa.Column("max_wait_days", sa.Integer(), nullable=False, server_default="60"))
    op.add_column("user", sa.Column("time_windows", sa.JSON()))
    op.add_column("user", sa.Column("preferred_pos", sa.JSON()))
