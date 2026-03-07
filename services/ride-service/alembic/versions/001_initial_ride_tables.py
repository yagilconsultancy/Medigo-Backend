"""Initial ride tables

Revision ID: 001
Revises:
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rides table
    op.create_table(
        "rides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rider_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("business_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("ride_type", sa.String(20), nullable=False),
        sa.Column("trip_type", sa.String(20), server_default="transport_only"),
        sa.Column("trip_structure", sa.String(20), server_default="one_way"),
        sa.Column("pickup_address", sa.Text, nullable=False),
        sa.Column("pickup_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("pickup_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("destination_address", sa.Text, nullable=False),
        sa.Column("destination_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("destination_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pickup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dropoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="requested", index=True),
        sa.Column("visit_type", sa.String(20), nullable=True),
        sa.Column("appointment_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("facility_name", sa.String(255), nullable=True),
        sa.Column("special_instructions", sa.Text, nullable=True),
        sa.Column("passenger_id", UUID(as_uuid=True), nullable=True),
        sa.Column("mobility_level", sa.String(30), nullable=True),
        sa.Column("assistance_level", sa.String(30), nullable=True),
        sa.Column("estimated_distance_miles", sa.Numeric(8, 2), nullable=True),
        sa.Column("actual_distance_miles", sa.Numeric(8, 2), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer, nullable=True),
        sa.Column("actual_duration_minutes", sa.Integer, nullable=True),
        sa.Column("estimated_fare", sa.Numeric(10, 2), nullable=True),
        sa.Column("final_fare", sa.Numeric(10, 2), nullable=True),
        sa.Column("cancelled_by", UUID(as_uuid=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(50), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recurring_ride_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Ride requests table
    op.create_table(
        "ride_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", UUID(as_uuid=True), sa.ForeignKey("rides.id"), nullable=False, index=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Ride ratings table
    op.create_table(
        "ride_ratings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", UUID(as_uuid=True), sa.ForeignKey("rides.id"), nullable=False, index=True),
        sa.Column("rated_user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("rated_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rating_type", sa.String(30), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Ride status logs table
    op.create_table(
        "ride_status_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", UUID(as_uuid=True), sa.ForeignKey("rides.id"), nullable=False, index=True),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("changed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notes", sa.Text, nullable=True),
    )

    # Recurring rides table
    op.create_table(
        "recurring_rides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("rider_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("pickup_address", sa.Text, nullable=False),
        sa.Column("destination_address", sa.Text, nullable=False),
        sa.Column("ride_type", sa.String(20), nullable=False),
        sa.Column("scheduled_time", sa.Time, nullable=False),
        sa.Column("days_of_week", ARRAY(sa.Integer), nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("recurring_rides")
    op.drop_table("ride_status_logs")
    op.drop_table("ride_ratings")
    op.drop_table("ride_requests")
    op.drop_table("rides")
