"""Support center admin + contact logs

Revision ID: 005
Revises: 004
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Sequences ──
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS support_ticket_seq START WITH 8795"))
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS contact_log_seq START WITH 1"))

    # ── Enhance support_tickets table ──
    op.add_column("support_tickets", sa.Column("ticket_number", sa.Integer(), nullable=True))
    op.add_column("support_tickets", sa.Column("ticket_type", sa.String(30), nullable=True))
    op.add_column("support_tickets", sa.Column("rider_id", UUID(as_uuid=True), nullable=True))
    op.add_column("support_tickets", sa.Column("rider_name", sa.String(200), nullable=True))
    op.add_column("support_tickets", sa.Column("driver_id", UUID(as_uuid=True), nullable=True))
    op.add_column("support_tickets", sa.Column("driver_name", sa.String(200), nullable=True))
    op.add_column("support_tickets", sa.Column("ride_id", UUID(as_uuid=True), nullable=True))
    op.add_column("support_tickets", sa.Column("assigned_to", UUID(as_uuid=True), nullable=True))
    op.add_column("support_tickets", sa.Column("resolved_by", UUID(as_uuid=True), nullable=True))

    # Backfill existing rows
    op.execute(sa.text(
        "UPDATE support_tickets "
        "SET ticket_number = nextval('support_ticket_seq'), "
        "    ticket_type = 'rider_complaint' "
        "WHERE ticket_number IS NULL"
    ))

    # Create indexes
    op.create_index("ix_support_tickets_ticket_number", "support_tickets", ["ticket_number"])
    op.create_index("ix_support_tickets_ticket_type", "support_tickets", ["ticket_type"])
    op.create_index("ix_support_tickets_rider_id", "support_tickets", ["rider_id"])
    op.create_index("ix_support_tickets_driver_id", "support_tickets", ["driver_id"])
    op.create_index("ix_support_tickets_ride_id", "support_tickets", ["ride_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])

    # ── Create contact_logs table ──
    op.create_table(
        "contact_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("contact_number", sa.Integer(), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_name", sa.String(200), nullable=False),
        sa.Column("user_role", sa.String(20), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), nullable=False),
        sa.Column("agent_name", sa.String(200), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contact_logs_contact_number", "contact_logs", ["contact_number"])
    op.create_index("ix_contact_logs_user_id", "contact_logs", ["user_id"])
    op.create_index("ix_contact_logs_channel", "contact_logs", ["channel"])


def downgrade() -> None:
    op.drop_table("contact_logs")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS contact_log_seq"))

    op.drop_index("ix_support_tickets_status", "support_tickets")
    op.drop_index("ix_support_tickets_ride_id", "support_tickets")
    op.drop_index("ix_support_tickets_driver_id", "support_tickets")
    op.drop_index("ix_support_tickets_rider_id", "support_tickets")
    op.drop_index("ix_support_tickets_ticket_type", "support_tickets")
    op.drop_index("ix_support_tickets_ticket_number", "support_tickets")

    op.drop_column("support_tickets", "resolved_by")
    op.drop_column("support_tickets", "assigned_to")
    op.drop_column("support_tickets", "ride_id")
    op.drop_column("support_tickets", "driver_name")
    op.drop_column("support_tickets", "driver_id")
    op.drop_column("support_tickets", "rider_name")
    op.drop_column("support_tickets", "rider_id")
    op.drop_column("support_tickets", "ticket_type")
    op.drop_column("support_tickets", "ticket_number")

    op.execute(sa.text("DROP SEQUENCE IF EXISTS support_ticket_seq"))
