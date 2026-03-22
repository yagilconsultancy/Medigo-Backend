"""Add admin_notes table for booking management.

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ride_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rides.id"),
            nullable=False,
        ),
        sa.Column("author_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "author_type", sa.String(20), nullable=False, server_default="admin"
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_admin_notes_ride_id", "admin_notes", ["ride_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_notes_ride_id", table_name="admin_notes")
    op.drop_table("admin_notes")
