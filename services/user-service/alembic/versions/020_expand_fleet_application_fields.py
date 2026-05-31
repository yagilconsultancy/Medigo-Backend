"""Expand fleet application fields for public submission

Revision ID: 020
Revises: 019
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Company Information
    op.add_column("fleet_applications", sa.Column("business_registration_number", sa.String(100), nullable=True))
    op.add_column("fleet_applications", sa.Column("years_in_operation", sa.Integer, nullable=True))
    op.add_column("fleet_applications", sa.Column("street_address", sa.String(500), nullable=True))
    op.add_column("fleet_applications", sa.Column("postal_code", sa.String(20), nullable=True))

    # Contact Information
    op.add_column("fleet_applications", sa.Column("contact_title", sa.String(255), nullable=True))
    op.add_column("fleet_applications", sa.Column("alternate_phone", sa.String(20), nullable=True))

    # Fleet Composition
    op.add_column("fleet_applications", sa.Column("average_vehicle_age", sa.Integer, nullable=True))
    op.add_column("fleet_applications", sa.Column("wheelchair_accessible_count", sa.Integer, server_default="0"))
    op.add_column("fleet_applications", sa.Column("stretcher_accessible_count", sa.Integer, server_default="0"))
    op.add_column("fleet_applications", sa.Column("ambulatory_vehicle_count", sa.Integer, server_default="0"))

    # Insurance & Compliance
    op.add_column("fleet_applications", sa.Column("insurance_provider", sa.String(255), nullable=True))
    op.add_column("fleet_applications", sa.Column("policy_number", sa.String(100), nullable=True))
    op.add_column("fleet_applications", sa.Column("liability_coverage_amount", sa.String(50), nullable=True))

    # Additional Information
    op.add_column("fleet_applications", sa.Column("service_areas", sa.Text, nullable=True))
    op.add_column("fleet_applications", sa.Column("healthcare_contracts", sa.Text, nullable=True))
    op.add_column("fleet_applications", sa.Column("additional_info", sa.Text, nullable=True))

    # Consent
    op.add_column("fleet_applications", sa.Column("consent_accuracy", sa.Boolean, server_default="false"))
    op.add_column("fleet_applications", sa.Column("consent_compliance", sa.Boolean, server_default="false"))
    op.add_column("fleet_applications", sa.Column("consent_contact", sa.Boolean, server_default="false"))


def downgrade() -> None:
    op.drop_column("fleet_applications", "consent_contact")
    op.drop_column("fleet_applications", "consent_compliance")
    op.drop_column("fleet_applications", "consent_accuracy")
    op.drop_column("fleet_applications", "additional_info")
    op.drop_column("fleet_applications", "healthcare_contracts")
    op.drop_column("fleet_applications", "service_areas")
    op.drop_column("fleet_applications", "liability_coverage_amount")
    op.drop_column("fleet_applications", "policy_number")
    op.drop_column("fleet_applications", "insurance_provider")
    op.drop_column("fleet_applications", "ambulatory_vehicle_count")
    op.drop_column("fleet_applications", "stretcher_accessible_count")
    op.drop_column("fleet_applications", "wheelchair_accessible_count")
    op.drop_column("fleet_applications", "average_vehicle_age")
    op.drop_column("fleet_applications", "alternate_phone")
    op.drop_column("fleet_applications", "contact_title")
    op.drop_column("fleet_applications", "postal_code")
    op.drop_column("fleet_applications", "street_address")
    op.drop_column("fleet_applications", "years_in_operation")
    op.drop_column("fleet_applications", "business_registration_number")
