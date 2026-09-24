"""add payment records for Stripe Checkout

Revision ID: 0008_stripe_payments
Revises: 0007_execution_pass_payment_flow
Create Date: 2026-09-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_stripe_payments"
down_revision: Union[str, None] = "0007_execution_pass_payment_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "booking_id", sa.Integer(), sa.ForeignKey("booking.id", ondelete="SET NULL")
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="created"),
        sa.Column("amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="cad"),
        sa.Column("provider_session_id", sa.String(255), unique=True),
        sa.Column("provider_payment_intent_id", sa.String(255)),
        sa.Column("provider_event_id", sa.String(255), unique=True),
        sa.Column("checkout_url", sa.Text()),
        sa.Column("metadata_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payment_user_id", "payment", ["user_id"])
    op.create_index("ix_payment_booking_id", "payment", ["booking_id"])
    op.create_index("ix_payment_status", "payment", ["status"])
    op.create_index("ix_payment_provider_session_id", "payment", ["provider_session_id"])
    op.create_index("ix_payment_provider_payment_intent_id", "payment", ["provider_payment_intent_id"])
    op.create_index("ix_payment_provider_event_id", "payment", ["provider_event_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_provider_event_id", table_name="payment")
    op.drop_index("ix_payment_provider_payment_intent_id", table_name="payment")
    op.drop_index("ix_payment_provider_session_id", table_name="payment")
    op.drop_index("ix_payment_status", table_name="payment")
    op.drop_index("ix_payment_booking_id", table_name="payment")
    op.drop_index("ix_payment_user_id", table_name="payment")
    op.drop_table("payment")
