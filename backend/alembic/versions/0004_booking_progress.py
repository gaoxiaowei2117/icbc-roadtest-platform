"""booking progress summary fields

Revision ID: 0004_booking_progress
Revises: 0003_email_verify
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_booking_progress"
down_revision: Union[str, None] = "0003_email_verify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "booking",
        sa.Column("progress_rounds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("booking", sa.Column("last_progress", sa.Text()))
    op.add_column("booking", sa.Column("last_progress_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("booking", "last_progress_at")
    op.drop_column("booking", "last_progress")
    op.drop_column("booking", "progress_rounds")
