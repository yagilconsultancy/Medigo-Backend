"""safety incidents

Revision ID: 007
Revises: 006
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sequences for human-readable IDs
    op.execute("CREATE SEQUENCE IF NOT EXISTS incident_seq START WITH 4300")
    op.execute("CREATE SEQUENCE IF NOT EXISTS alert_seq START WITH 430")
    op.execute("CREATE SEQUENCE IF NOT EXISTS investigation_seq START WITH 2190")
    op.execute("CREATE SEQUENCE IF NOT EXISTS disciplinary_seq START WITH 1190")

    # incidents table
    op.create_table(
        "incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("incident_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="under_investigation"),
        sa.Column("subject_name", sa.String(200), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=True),
        sa.Column("subject_type", sa.String(10), nullable=False),
        sa.Column("filed_by_name", sa.String(200), nullable=False),
        sa.Column("filed_by_id", UUID(as_uuid=True), nullable=True),
        sa.Column("filed_by_role", sa.String(20), nullable=False, server_default="admin"),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # incident_notes table
    op.create_table(
        "incident_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=False, index=True),
        sa.Column("author_id", UUID(as_uuid=True), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # safety_alerts table
    op.create_table(
        "safety_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("alert_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("driver_id", UUID(as_uuid=True), nullable=True),
        sa.Column("driver_name", sa.String(200), nullable=True),
        sa.Column("ride_id", UUID(as_uuid=True), nullable=True),
        sa.Column("trip_display_id", sa.String(20), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # investigations table
    op.create_table(
        "investigations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("investigation_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=False, index=True),
        sa.Column("incident_number", sa.Integer(), nullable=False),
        sa.Column("incident_type", sa.String(30), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(30), nullable=False, server_default="unassigned"),
        sa.Column("subject_name", sa.String(200), nullable=False),
        sa.Column("assigned_to_id", UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_to_name", sa.String(200), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # investigation_notes table
    op.create_table(
        "investigation_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("investigation_id", UUID(as_uuid=True), sa.ForeignKey("investigations.id"), nullable=False, index=True),
        sa.Column("author_id", UUID(as_uuid=True), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # disciplinary_actions table
    op.create_table(
        "disciplinary_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("action_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("incident_id", UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("incident_number", sa.Integer(), nullable=True),
        sa.Column("investigation_id", UUID(as_uuid=True), sa.ForeignKey("investigations.id"), nullable=True),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="issued"),
        sa.Column("subject_name", sa.String(200), nullable=False),
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subject_type", sa.String(10), nullable=False),
        sa.Column("issued_by_name", sa.String(200), nullable=False),
        sa.Column("issued_by_id", UUID(as_uuid=True), nullable=False),
        sa.Column("duration_text", sa.String(50), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reinstated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("disciplinary_actions")
    op.drop_table("investigation_notes")
    op.drop_table("investigations")
    op.drop_table("safety_alerts")
    op.drop_table("incident_notes")
    op.drop_table("incidents")
    op.execute("DROP SEQUENCE IF EXISTS disciplinary_seq")
    op.execute("DROP SEQUENCE IF EXISTS investigation_seq")
    op.execute("DROP SEQUENCE IF EXISTS alert_seq")
    op.execute("DROP SEQUENCE IF EXISTS incident_seq")
