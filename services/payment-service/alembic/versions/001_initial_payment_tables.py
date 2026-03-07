"""Initial payment tables

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
    # Payment methods table (must be created first due to FK reference)
    op.create_table(
        "payment_methods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("method_type", sa.String(30), nullable=False),
        sa.Column("last_four", sa.String(4), nullable=False),
        sa.Column("brand", sa.String(50), nullable=True),
        sa.Column("holder_name", sa.String(200), nullable=False),
        sa.Column("is_default", sa.Boolean, server_default="false"),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Transactions table
    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("reference_id", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Fare breakdowns table
    op.create_table(
        "fare_breakdowns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column("base_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("distance_charge", sa.Numeric(10, 2), server_default="0"),
        sa.Column("medical_assist_premium", sa.Numeric(10, 2), server_default="0"),
        sa.Column("service_fee", sa.Numeric(10, 2), server_default="0"),
        sa.Column("platform_fee", sa.Numeric(10, 2), server_default="0"),
        sa.Column("tips", sa.Numeric(10, 2), server_default="0"),
        sa.Column("incentives_bonuses", sa.Numeric(10, 2), server_default="0"),
        sa.Column("total_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("driver_earnings", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Driver earnings table
    op.create_table(
        "driver_earnings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False, unique=True, index=True),
        sa.Column("available_balance", sa.Numeric(10, 2), server_default="0"),
        sa.Column("total_earned", sa.Numeric(10, 2), server_default="0"),
        sa.Column("total_withdrawn", sa.Numeric(10, 2), server_default="0"),
        sa.Column("pending_withdrawal", sa.Numeric(10, 2), server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Withdrawals table
    op.create_table(
        "withdrawals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("transaction_fee", sa.Numeric(10, 2), server_default="0"),
        sa.Column("net_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("payment_method_id", UUID(as_uuid=True), sa.ForeignKey("payment_methods.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Earnings periods table
    op.create_table(
        "earnings_periods",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("period_type", sa.String(10), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("total_earnings", sa.Numeric(10, 2), server_default="0"),
        sa.Column("trip_count", sa.Integer, server_default="0"),
        sa.Column("hours_online", sa.Numeric(6, 2), server_default="0"),
        sa.Column("base_fares", sa.Numeric(10, 2), server_default="0"),
        sa.Column("distance_charges", sa.Numeric(10, 2), server_default="0"),
        sa.Column("medical_premiums", sa.Numeric(10, 2), server_default="0"),
        sa.Column("tips", sa.Numeric(10, 2), server_default="0"),
        sa.Column("incentives", sa.Numeric(10, 2), server_default="0"),
        sa.Column("platform_fees", sa.Numeric(10, 2), server_default="0"),
        sa.Column("net_earnings", sa.Numeric(10, 2), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("driver_id", "period_type", "period_start", name="uq_driver_period"),
    )


def downgrade() -> None:
    op.drop_table("earnings_periods")
    op.drop_table("withdrawals")
    op.drop_table("driver_earnings")
    op.drop_table("fare_breakdowns")
    op.drop_table("transactions")
    op.drop_table("payment_methods")
