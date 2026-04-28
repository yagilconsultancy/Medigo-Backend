"""guest booking sessions

Revision ID: 012
Revises: 011
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_booking_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rider_id", UUID(as_uuid=True), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_guest_booking_sessions_rider_id",
        "guest_booking_sessions",
        ["rider_id"],
    )
    op.add_column(
        "rides",
        sa.Column("guest_session_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_rides_guest_session_id", "rides", ["guest_session_id"])


def downgrade() -> None:
    op.drop_index("ix_rides_guest_session_id", table_name="rides")
    op.drop_column("rides", "guest_session_id")
    op.drop_index(
        "ix_guest_booking_sessions_rider_id",
        table_name="guest_booking_sessions",
    )
    op.drop_table("guest_booking_sessions")
