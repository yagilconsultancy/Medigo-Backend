"""Add share_token column to rides table.

Revision ID: 003
Revises: 002
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("share_token", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_rides_share_token", "rides", ["share_token"])
    op.create_index("ix_rides_share_token", "rides", ["share_token"])


def downgrade() -> None:
    op.drop_index("ix_rides_share_token", table_name="rides")
    op.drop_constraint("uq_rides_share_token", "rides", type_="unique")
    op.drop_column("rides", "share_token")
