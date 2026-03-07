"""Add user settings table

Revision ID: 004
Revises: 003
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        # Notification settings
        sa.Column("push_ride_updates", sa.Boolean, server_default="true"),
        sa.Column("push_chat_messages", sa.Boolean, server_default="true"),
        sa.Column("push_earnings", sa.Boolean, server_default="true"),
        sa.Column("push_promotions", sa.Boolean, server_default="true"),
        sa.Column("email_ride_receipts", sa.Boolean, server_default="true"),
        sa.Column("email_weekly_summary", sa.Boolean, server_default="true"),
        sa.Column("sms_ride_updates", sa.Boolean, server_default="false"),
        # Privacy settings
        sa.Column("share_location_with_rider", sa.Boolean, server_default="true"),
        sa.Column("show_profile_photo", sa.Boolean, server_default="true"),
        sa.Column("show_rating", sa.Boolean, server_default="true"),
        sa.Column("allow_data_analytics", sa.Boolean, server_default="true"),
        # App settings
        sa.Column("language", sa.String(10), server_default="en"),
        sa.Column("distance_unit", sa.String(10), server_default="miles"),
        sa.Column("theme", sa.String(10), server_default="system"),
        sa.Column("auto_accept_rides", sa.Boolean, server_default="false"),
        sa.Column("navigation_app", sa.String(20), server_default="google_maps"),
        sa.Column("sound_enabled", sa.Boolean, server_default="true"),
        # Timestamp
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
