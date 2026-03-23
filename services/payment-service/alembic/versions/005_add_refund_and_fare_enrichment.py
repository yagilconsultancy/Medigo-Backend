"""Add refund_requests table and ride_type/pickup_city to fare_breakdowns.

Revision ID: 005
Revises: 004
Create Date: 2026-03-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create refund_requests table
    op.create_table(
        "refund_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("transaction_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("rider_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("refund_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_partial", sa.Boolean(), default=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), default="pending", index=True),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("stripe_refund_id", sa.String(255), nullable=True),
        sa.Column("refund_transaction_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ride_type", sa.String(50), nullable=True),
        sa.Column("payment_method_type", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Add denormalized columns to fare_breakdowns for admin analytics
    op.add_column("fare_breakdowns", sa.Column("ride_type", sa.String(50), nullable=True))
    op.add_column("fare_breakdowns", sa.Column("pickup_city", sa.String(200), nullable=True))
    op.create_index("ix_fare_breakdowns_ride_type", "fare_breakdowns", ["ride_type"])
    op.create_index("ix_fare_breakdowns_pickup_city", "fare_breakdowns", ["pickup_city"])


def downgrade() -> None:
    op.drop_index("ix_fare_breakdowns_pickup_city", "fare_breakdowns")
    op.drop_index("ix_fare_breakdowns_ride_type", "fare_breakdowns")
    op.drop_column("fare_breakdowns", "pickup_city")
    op.drop_column("fare_breakdowns", "ride_type")
    op.drop_table("refund_requests")
