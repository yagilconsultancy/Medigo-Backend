"""Initial chat tables

Revision ID: 001
Revises:
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Conversations table
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("rider_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Messages table
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False, index=True),
        sa.Column("sender_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("message_type", sa.String(20), server_default="text"),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Message reactions table
    op.create_table(
        "message_reactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False, index=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("emoji", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("message_reactions")
    op.drop_table("messages")
    op.drop_table("conversations")
