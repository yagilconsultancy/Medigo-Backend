"""Add dispute tables.

Revision ID: 010
Revises: 009
Create Date: 2026-05-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS dispute_seq START WITH 1000"))

    op.create_table(
        "disputes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("dispute_number", sa.Integer(), nullable=False),
        sa.Column("dispute_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'under_review'")),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rider_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rider_name", sa.String(length=200), nullable=False),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=True),
        sa.Column("driver_name", sa.String(length=200), nullable=True),
        sa.Column("trip_code", sa.String(length=50), nullable=False),
        sa.Column("billed_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("claimed_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("refund_request_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("dispute_number", name="uq_disputes_dispute_number"),
    )
    op.create_index("ix_disputes_dispute_number", "disputes", ["dispute_number"])
    op.create_index("ix_disputes_dispute_type", "disputes", ["dispute_type"])
    op.create_index("ix_disputes_status", "disputes", ["status"])
    op.create_index("ix_disputes_ride_id", "disputes", ["ride_id"])
    op.create_index("ix_disputes_rider_id", "disputes", ["rider_id"])
    op.create_index("ix_disputes_driver_id", "disputes", ["driver_id"])
    op.create_index("ix_disputes_trip_code", "disputes", ["trip_code"])
    op.create_index("ix_disputes_refund_request_id", "disputes", ["refund_request_id"])

    op.create_table(
        "dispute_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("dispute_id", UUID(as_uuid=True), sa.ForeignKey("disputes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admin_id", UUID(as_uuid=True), nullable=False),
        sa.Column("admin_name", sa.String(length=200), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_dispute_notes_dispute_id", "dispute_notes", ["dispute_id"])


def downgrade() -> None:
    op.drop_index("ix_dispute_notes_dispute_id", table_name="dispute_notes")
    op.drop_table("dispute_notes")

    op.drop_index("ix_disputes_refund_request_id", table_name="disputes")
    op.drop_index("ix_disputes_trip_code", table_name="disputes")
    op.drop_index("ix_disputes_driver_id", table_name="disputes")
    op.drop_index("ix_disputes_rider_id", table_name="disputes")
    op.drop_index("ix_disputes_ride_id", table_name="disputes")
    op.drop_index("ix_disputes_status", table_name="disputes")
    op.drop_index("ix_disputes_dispute_type", table_name="disputes")
    op.drop_index("ix_disputes_dispute_number", table_name="disputes")
    op.drop_table("disputes")

    op.execute(sa.text("DROP SEQUENCE IF EXISTS dispute_seq"))
