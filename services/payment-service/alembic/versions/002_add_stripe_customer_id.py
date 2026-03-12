"""Add stripe_customer_id to payment_methods

Revision ID: 002
Revises: 001
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_methods",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payment_methods", "stripe_customer_id")
