"""Add highway 407 toll and dialysis trip fields to rides.

Revision ID: 005
Revises: 004
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rides", sa.Column("use_highway_407", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("rides", sa.Column("highway_407_route", sa.String(50), nullable=True))
    op.add_column("rides", sa.Column("is_dialysis_trip", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("rides", "is_dialysis_trip")
    op.drop_column("rides", "highway_407_route")
    op.drop_column("rides", "use_highway_407")
