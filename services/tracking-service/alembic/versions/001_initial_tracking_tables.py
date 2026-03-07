"""Initial tracking tables

Revision ID: 001
Revises:
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tracking_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("rider_id", UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("current_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("current_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("current_heading", sa.Numeric(5, 1), nullable=True),
        sa.Column("current_speed", sa.Numeric(5, 1), nullable=True),
        sa.Column("eta_minutes", sa.Numeric(6, 1), nullable=True),
        sa.Column("distance_remaining_miles", sa.Numeric(8, 2), nullable=True),
        sa.Column("pickup_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("pickup_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("destination_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("destination_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index(
        "ix_tracking_sessions_ride_status",
        "tracking_sessions",
        ["ride_id", "status"],
    )

    op.create_table(
        "location_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("tracking_sessions.id"), nullable=False, index=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("heading", sa.Numeric(5, 1), nullable=True),
        sa.Column("speed", sa.Numeric(5, 1), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("location_history")
    op.drop_index("ix_tracking_sessions_ride_status", table_name="tracking_sessions")
    op.drop_table("tracking_sessions")
