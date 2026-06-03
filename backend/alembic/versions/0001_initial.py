"""initial schema: user, secret, booking

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-02

说明：用 sa.JSON() 替代 postgresql.ARRAY/JSONB，使 schema 可在 sqlite 上本地
开发；JSON 列在 postgres 上映射为 JSON（非 JSONB）以保证可移植性。应用层负责
数组/字典的序列化（SQLAlchemy 2.0 的 Mapped[list|dict] 自动处理）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("icbc_license_no", sa.String(50)),
        sa.Column("icbc_last_name", sa.String(100)),
        sa.Column("preferred_pos", sa.JSON()),
        sa.Column("time_windows", sa.JSON()),
        sa.Column("max_wait_days", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_user_email"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)

    op.create_table(
        "secret",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", name="uq_secret_user_id"),
    )
    op.create_index("ix_secret_user_id", "secret", ["user_id"], unique=True)

    op.create_table(
        "booking",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("target_date", sa.Date()),
        sa.Column("time_window", sa.JSON()),
        sa.Column("pos_code", sa.String(50)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("result", sa.JSON()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_booking_user_id", "booking", ["user_id"])
    op.create_index("ix_booking_status", "booking", ["status"])


def downgrade() -> None:
    op.drop_index("ix_booking_status", table_name="booking")
    op.drop_index("ix_booking_user_id", table_name="booking")
    op.drop_table("booking")
    op.drop_index("ix_secret_user_id", table_name="secret")
    op.drop_table("secret")
    op.drop_index("ix_user_email", table_name="user")
    op.drop_table("user")
