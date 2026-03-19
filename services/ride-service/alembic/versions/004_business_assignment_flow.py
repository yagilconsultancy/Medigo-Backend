"""Add business assignment columns and rename ride types.

Revision ID: 004
Revises: 003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Widen status columns to fit "pending_business_assignment" (29 chars)
    op.alter_column("rides", "status",
                     type_=sa.String(40), existing_type=sa.String(20))
    op.alter_column("ride_status_logs", "from_status",
                     type_=sa.String(40), existing_type=sa.String(20))
    op.alter_column("ride_status_logs", "to_status",
                     type_=sa.String(40), existing_type=sa.String(20))

    # 2. Widen trip_type to fit "transport_care_assistant" (25 chars)
    op.alter_column("rides", "trip_type",
                     type_=sa.String(30), existing_type=sa.String(20))

    # 3. Add business assignment columns
    op.add_column("rides", sa.Column(
        "assigned_to_business_id", UUID(as_uuid=True), nullable=True))
    op.add_column("rides", sa.Column(
        "assigned_by_admin_id", UUID(as_uuid=True), nullable=True))
    op.add_column("rides", sa.Column(
        "assigned_to_business_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rides", sa.Column(
        "business_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rides", sa.Column(
        "business_assignment_expires_at", sa.DateTime(timezone=True), nullable=True))

    # 4. Add index on assigned_to_business_id
    op.create_index(
        "ix_rides_assigned_to_business_id", "rides", ["assigned_to_business_id"])

    # 5. Data migration: rename ride_type STANDARD -> AMBULATORY
    op.execute("UPDATE rides SET ride_type = 'ambulatory' WHERE ride_type = 'standard'")
    op.execute(
        "UPDATE recurring_rides SET ride_type = 'ambulatory' WHERE ride_type = 'standard'")

    # 6. Data migration: rename trip_type TRANSPORT_ESCORT -> TRANSPORT_CARE_ASSISTANT
    op.execute(
        "UPDATE rides SET trip_type = 'transport_care_assistant' "
        "WHERE trip_type = 'transport_escort'"
    )


def downgrade() -> None:
    # Reverse data migrations
    op.execute(
        "UPDATE rides SET trip_type = 'transport_escort' "
        "WHERE trip_type = 'transport_care_assistant'"
    )
    op.execute(
        "UPDATE recurring_rides SET ride_type = 'standard' WHERE ride_type = 'ambulatory'")
    op.execute("UPDATE rides SET ride_type = 'standard' WHERE ride_type = 'ambulatory'")

    # Drop index and columns
    op.drop_index("ix_rides_assigned_to_business_id", table_name="rides")
    op.drop_column("rides", "business_assignment_expires_at")
    op.drop_column("rides", "business_accepted_at")
    op.drop_column("rides", "assigned_to_business_at")
    op.drop_column("rides", "assigned_by_admin_id")
    op.drop_column("rides", "assigned_to_business_id")

    # Restore original column widths
    op.alter_column("rides", "trip_type",
                     type_=sa.String(20), existing_type=sa.String(30))
    op.alter_column("ride_status_logs", "to_status",
                     type_=sa.String(20), existing_type=sa.String(40))
    op.alter_column("ride_status_logs", "from_status",
                     type_=sa.String(20), existing_type=sa.String(40))
    op.alter_column("rides", "status",
                     type_=sa.String(20), existing_type=sa.String(40))
