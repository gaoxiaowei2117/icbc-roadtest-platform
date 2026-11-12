"""add payment kind and route pack purchases

Revision ID: 0009_route_packs
Revises: 0008_stripe_payments
Create Date: 2026-11-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_route_packs"
down_revision: Union[str, None] = "0008_stripe_payments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payment",
        sa.Column("kind", sa.String(20), nullable=False, server_default="execution_pass"),
    )
    op.add_column("payment", sa.Column("product_ref", sa.String(64)))
    op.create_index("ix_payment_kind", "payment", ["kind"])

    op.create_table(
        "route_pack_purchase",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("pack_slug", sa.String(64), nullable=False),
        sa.Column(
            "payment_id", sa.Integer(), sa.ForeignKey("payment.id", ondelete="SET NULL")
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("granted_by", sa.Integer(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "pack_slug", name="uq_route_pack_purchase_user_pack"),
    )
    op.create_index("ix_route_pack_purchase_user_id", "route_pack_purchase", ["user_id"])
    op.create_index("ix_route_pack_purchase_pack_slug", "route_pack_purchase", ["pack_slug"])
    op.create_index("ix_route_pack_purchase_payment_id", "route_pack_purchase", ["payment_id"])
    op.create_index("ix_route_pack_purchase_status", "route_pack_purchase", ["status"])


def downgrade() -> None:
    op.drop_index("ix_route_pack_purchase_status", table_name="route_pack_purchase")
    op.drop_index("ix_route_pack_purchase_payment_id", table_name="route_pack_purchase")
    op.drop_index("ix_route_pack_purchase_pack_slug", table_name="route_pack_purchase")
    op.drop_index("ix_route_pack_purchase_user_id", table_name="route_pack_purchase")
    op.drop_table("route_pack_purchase")
    op.drop_index("ix_payment_kind", table_name="payment")
    op.drop_column("payment", "product_ref")
    op.drop_column("payment", "kind")
