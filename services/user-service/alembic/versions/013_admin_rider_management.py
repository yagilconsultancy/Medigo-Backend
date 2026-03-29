"""admin rider management

Revision ID: 013
Revises: 012
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Add columns to users ---
    op.add_column("users", sa.Column("insurance_provider", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("insurance_policy_number", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("suspension_reason", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("suspended_by", UUID(as_uuid=True), nullable=True))

    # --- Create rider_issue_ticket_seq ---
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS rider_issue_ticket_seq START WITH 8800"))

    # --- Create rider_issues table ---
    op.create_table(
        "rider_issues",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ticket_number",
            sa.Integer(),
            server_default=sa.text("nextval('rider_issue_ticket_seq')"),
            nullable=False,
        ),
        sa.Column("rider_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("issue_type", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("assigned_to", UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Create rider_issue_notes table ---
    op.create_table(
        "rider_issue_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "issue_id", UUID(as_uuid=True), sa.ForeignKey("rider_issues.id"), nullable=False, index=True
        ),
        sa.Column("author_id", UUID(as_uuid=True), nullable=False),
        sa.Column("note_text", sa.Text(), nullable=False),
        sa.Column("action", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("rider_issue_notes")
    op.drop_table("rider_issues")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS rider_issue_ticket_seq"))
    op.drop_column("users", "suspended_by")
    op.drop_column("users", "suspension_reason")
    op.drop_column("users", "suspended_at")
    op.drop_column("users", "insurance_policy_number")
    op.drop_column("users", "insurance_provider")
