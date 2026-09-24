"""store the original email for the configured ICBC driver

Revision ID: 0006_icbc_original_email
Revises: 0005_one_active_booking
Create Date: 2026-08-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_icbc_original_email"
down_revision: Union[str, None] = "0005_one_active_booking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("icbc_original_email", sa.String(255)))


def downgrade() -> None:
    op.drop_column("user", "icbc_original_email")
