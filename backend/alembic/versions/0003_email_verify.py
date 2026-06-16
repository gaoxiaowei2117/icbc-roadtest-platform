"""email verification: user 加 email_verified/verify_code/verify_code_expires

Revision ID: 0003_email_verify
Revises: 0002_multiuser_profile
Create Date: 2026-06-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_email_verify"
down_revision: Union[str, None] = "0002_multiuser_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("user", sa.Column("verify_code", sa.String(6)))
    op.add_column("user", sa.Column("verify_code_expires", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("user", "verify_code_expires")
    op.drop_column("user", "verify_code")
    op.drop_column("user", "email_verified")
