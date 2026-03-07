"""Add saved locations table

Revision ID: 006
Revises: 005
Create Date: 2026-03-07
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
        "saved_locations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("location_type", sa.String(20), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("place_id", sa.String(300), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_default", sa.Boolean, server_default="false"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_saved_locations_user_id", "saved_locations", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_locations_user_id")
    op.drop_table("saved_locations")
