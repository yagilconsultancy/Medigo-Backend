"""Add specialty column to driver_profiles

Revision ID: 008
Revises: 007
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("driver_profiles", sa.Column("specialty", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("driver_profiles", "specialty")
