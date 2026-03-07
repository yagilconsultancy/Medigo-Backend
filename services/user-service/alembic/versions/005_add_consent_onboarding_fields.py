"""Add consent, onboarding, home_address, medical_notes to users table.

Revision ID: 005
Revises: 004
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("home_address", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("medical_notes", sa.Text, nullable=True))

    # Consent fields
    op.add_column(
        "users",
        sa.Column("consent_emergency_services", sa.Boolean, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("consent_privacy_policy", sa.Boolean, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("consent_terms_of_service", sa.Boolean, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("consent_data_location", sa.Boolean, server_default="false"),
    )
    op.add_column(
        "users",
        sa.Column("consent_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Onboarding tracking
    op.add_column(
        "users", sa.Column("onboarding_step", sa.Integer, server_default="1")
    )
    op.add_column(
        "users",
        sa.Column("onboarding_completed", sa.Boolean, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed")
    op.drop_column("users", "onboarding_step")
    op.drop_column("users", "consent_accepted_at")
    op.drop_column("users", "consent_data_location")
    op.drop_column("users", "consent_terms_of_service")
    op.drop_column("users", "consent_privacy_policy")
    op.drop_column("users", "consent_emergency_services")
    op.drop_column("users", "medical_notes")
    op.drop_column("users", "home_address")
