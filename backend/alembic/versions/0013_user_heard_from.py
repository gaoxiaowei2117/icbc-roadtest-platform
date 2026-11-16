"""user.heard_from: post-purchase "how did you hear about us?" answer

Revision ID: 0013_user_heard_from
Revises: 0012_user_signup_source
"""
import sqlalchemy as sa
from alembic import op

revision = "0013_user_heard_from"
down_revision = "0012_user_signup_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("heard_from", sa.String(40), nullable=True))
    op.add_column("user", sa.Column("heard_from_detail", sa.String(200), nullable=True))
    op.add_column("user", sa.Column("heard_from_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "heard_from_at")
    op.drop_column("user", "heard_from_detail")
    op.drop_column("user", "heard_from")
