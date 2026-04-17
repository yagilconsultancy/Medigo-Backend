"""add dispute tables

Revision ID: 010_add_dispute_tables
Revises: 009_caregiver_commission_config
Create Date: 2026-04-17

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "010_add_dispute_tables"
down_revision = "009_caregiver_commission_config"
branch_label = None
depends_on = None


def upgrade() -> None:
    # Create dispute_seq sequence for DIS-XXXX numbering (starting at 3298 based on screenshot)
    op.execute("CREATE SEQUENCE dispute_seq START WITH 3298;")

    # Create disputes table
    op.create_table(
        "disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dispute_number", sa.Integer(), nullable=False),
        sa.Column("dispute_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("ride_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rider_name", sa.String(length=200), nullable=False),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("driver_name", sa.String(length=200), nullable=True),
        sa.Column("trip_code", sa.String(length=50), nullable=False),
        sa.Column("billed_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("claimed_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("refund_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_disputes_dispute_number"), "disputes", ["dispute_number"], unique=True)
    op.create_index(op.f("ix_disputes_dispute_type"), "disputes", ["dispute_type"], unique=False)
    op.create_index(op.f("ix_disputes_driver_id"), "disputes", ["driver_id"], unique=False)
    op.create_index(op.f("ix_disputes_refund_request_id"), "disputes", ["refund_request_id"], unique=False)
    op.create_index(op.f("ix_disputes_ride_id"), "disputes", ["ride_id"], unique=False)
    op.create_index(op.f("ix_disputes_rider_id"), "disputes", ["rider_id"], unique=False)
    op.create_index(op.f("ix_disputes_status"), "disputes", ["status"], unique=False)
    op.create_index(op.f("ix_disputes_trip_code"), "disputes", ["trip_code"], unique=False)

    # Create dispute_notes table
    op.create_table(
        "dispute_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dispute_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_name", sa.String(length=200), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dispute_notes_dispute_id"), "dispute_notes", ["dispute_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dispute_notes_dispute_id"), table_name="dispute_notes")
    op.drop_table("dispute_notes")
    op.drop_index(op.f("ix_disputes_trip_code"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_status"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_rider_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_ride_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_refund_request_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_driver_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_dispute_type"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_dispute_number"), table_name="disputes")
    op.drop_table("disputes")
    op.execute("DROP SEQUENCE IF EXISTS dispute_seq;")
