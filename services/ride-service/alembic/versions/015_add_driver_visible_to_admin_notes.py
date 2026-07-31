"""Add is_driver_visible flag to admin_notes.

Lets an admin mark a booking note as something the assigned driver should see,
so driver instructions no longer have to be written into the rider's own
special_instructions field (which would overwrite it).

Revision ID: 015
Revises: 014
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_notes",
        sa.Column(
            "is_driver_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("admin_notes", "is_driver_visible")
