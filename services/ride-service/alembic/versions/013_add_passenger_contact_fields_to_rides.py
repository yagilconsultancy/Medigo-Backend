"""add passenger contact fields to rides

Revision ID: 013
Revises: 012
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rides",
        sa.Column("passenger_first_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "rides",
        sa.Column("passenger_last_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "rides",
        sa.Column("passenger_phone", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("rides", "passenger_phone")
    op.drop_column("rides", "passenger_last_name")
    op.drop_column("rides", "passenger_first_name")
