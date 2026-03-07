"""Add notifications table for in-app notification inbox

Revision ID: 003
Revises: 002
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("notification_type", sa.String(30), nullable=False),
        sa.Column("data", JSON, nullable=True),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_type", "notifications", ["notification_type"])
    op.create_index("ix_notifications_is_read", "notifications", ["is_read"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])
    op.create_index(
        "ix_notifications_user_unread",
        "notifications",
        ["user_id", "is_read", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_user_unread")
    op.drop_index("ix_notifications_created_at")
    op.drop_index("ix_notifications_is_read")
    op.drop_index("ix_notifications_type")
    op.drop_index("ix_notifications_user_id")
    op.drop_table("notifications")
