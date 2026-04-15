"""increase visit_type column length

Revision ID: 011
Revises: 010
Create Date: 2026-04-15 22:57:00

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Increase visit_type column from VARCHAR(20) to VARCHAR(100)
    # to accommodate longer medical appointment type descriptions
    op.alter_column(
        "rides",
        "visit_type",
        type_=sa.String(100),
        existing_type=sa.String(20),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Revert to VARCHAR(20)
    op.alter_column(
        "rides",
        "visit_type",
        type_=sa.String(20),
        existing_type=sa.String(100),
        existing_nullable=True,
    )
