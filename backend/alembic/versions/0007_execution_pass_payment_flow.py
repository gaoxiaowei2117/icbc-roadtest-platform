"""add one-time execution passes and payment review workflow

Revision ID: 0007_execution_pass_payment_flow
Revises: 0006_icbc_original_email
Create Date: 2026-08-08
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_execution_pass_payment_flow"
down_revision: Union[str, None] = "0006_icbc_original_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "booking",
        sa.Column(
            "payment_status",
            sa.String(20),
            nullable=False,
            server_default="not_required",
        ),
    )
    op.add_column("booking", sa.Column("payment_reference", sa.Text()))
    op.add_column(
        "booking", sa.Column("payment_submitted_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "booking",
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL")),
    )
    op.add_column("booking", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.add_column("booking", sa.Column("review_reason", sa.Text()))
    op.create_index("ix_booking_payment_status", "booking", ["payment_status"])

    op.create_table(
        "execution_pass",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "booking_id",
            sa.Integer(),
            sa.ForeignKey("booking.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column(
            "approved_by", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL")
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("booking_id", name="uq_execution_pass_booking_id"),
    )
    op.create_index("ix_execution_pass_user_id", "execution_pass", ["user_id"])
    op.create_index("ix_execution_pass_booking_id", "execution_pass", ["booking_id"])
    op.create_index("ix_execution_pass_status", "execution_pass", ["status"])

    # Extend the existing database-level one-active-task invariant to include
    # the payment and admin-review waiting states.
    op.drop_index("uq_booking_one_active_per_user", table_name="booking")
    op.create_index(
        "uq_booking_one_active_per_user",
        "booking",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('awaiting_payment', 'awaiting_review', 'pending', 'running')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_booking_one_active_per_user", table_name="booking")
    op.create_index(
        "uq_booking_one_active_per_user",
        "booking",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )
    op.drop_index("ix_execution_pass_status", table_name="execution_pass")
    op.drop_index("ix_execution_pass_booking_id", table_name="execution_pass")
    op.drop_index("ix_execution_pass_user_id", table_name="execution_pass")
    op.drop_table("execution_pass")
    op.drop_index("ix_booking_payment_status", table_name="booking")
    op.drop_column("booking", "review_reason")
    op.drop_column("booking", "reviewed_at")
    op.drop_column("booking", "reviewed_by")
    op.drop_column("booking", "payment_submitted_at")
    op.drop_column("booking", "payment_reference")
    op.drop_column("booking", "payment_status")
