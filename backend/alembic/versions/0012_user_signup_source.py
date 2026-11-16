"""user.signup_source / signup_detail / signup_landing: where a sign-up came from

Revision ID: 0012_user_signup_source
Revises: 0011_user_exclude_from_stats
Create Date: 2026-11-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_user_signup_source"
down_revision: Union[str, None] = "0011_user_exclude_from_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("signup_source", sa.String(length=40), nullable=True))
    op.add_column("user", sa.Column("signup_detail", sa.String(length=200), nullable=True))
    op.add_column("user", sa.Column("signup_landing", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "signup_landing")
    op.drop_column("user", "signup_detail")
    op.drop_column("user", "signup_source")
