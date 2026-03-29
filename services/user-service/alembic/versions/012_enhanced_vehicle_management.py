"""Enhanced vehicle management - vehicle documents, category configs, new columns

Revision ID: 012
Revises: 011
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Add columns to vehicles ---
    op.add_column("vehicles", sa.Column("passenger_capacity", sa.Integer(), nullable=True))
    op.add_column("vehicles", sa.Column("special_equipment", JSON(), nullable=True))
    op.add_column("vehicles", sa.Column("insurance_provider", sa.String(255), nullable=True))
    op.add_column("vehicles", sa.Column("registration_authority", sa.String(255), nullable=True))
    op.add_column("vehicles", sa.Column("last_inspection_date", sa.Date(), nullable=True))
    op.add_column("vehicles", sa.Column("internal_notes", sa.Text(), nullable=True))

    # --- Add columns to vehicle_maintenance_logs ---
    op.add_column("vehicle_maintenance_logs", sa.Column("service_type", sa.String(50), nullable=True))
    op.add_column("vehicle_maintenance_logs", sa.Column("technician_notes", sa.Text(), nullable=True))

    # --- Create vehicle_documents table ---
    op.create_table(
        "vehicle_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", UUID(as_uuid=True), sa.ForeignKey("vehicles.id"), nullable=False, index=True),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("file_key", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="valid"),
        sa.Column("uploaded_by", UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Create vehicle_category_configs table ---
    op.create_table(
        "vehicle_category_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("category", sa.String(30), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("base_fare", sa.Numeric(10, 2), nullable=False),
        sa.Column("per_km_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("requirements", JSON(), server_default="[]"),
        sa.Column("common_vehicles", JSON(), server_default="[]"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Seed category configs ---
    op.execute(
        sa.text(
            """
            INSERT INTO vehicle_category_configs (id, category, display_name, base_fare, per_km_rate, requirements, common_vehicles)
            VALUES
            (
                gen_random_uuid(),
                'standard',
                'Standard Ride',
                CAST(:std_base AS NUMERIC(10,2)),
                CAST(:std_km AS NUMERIC(10,2)),
                CAST(:std_req AS JSON),
                CAST(:std_vehicles AS JSON)
            ),
            (
                gen_random_uuid(),
                'wheelchair_accessible',
                'Wheelchair Accessible',
                CAST(:wav_base AS NUMERIC(10,2)),
                CAST(:wav_km AS NUMERIC(10,2)),
                CAST(:wav_req AS JSON),
                CAST(:wav_vehicles AS JSON)
            ),
            (
                gen_random_uuid(),
                'assisted_ride',
                'Assisted Ride',
                CAST(:ast_base AS NUMERIC(10,2)),
                CAST(:ast_km AS NUMERIC(10,2)),
                CAST(:ast_req AS JSON),
                CAST(:ast_vehicles AS JSON)
            ),
            (
                gen_random_uuid(),
                'stretcher_transport',
                'Stretcher Transport',
                CAST(:str_base AS NUMERIC(10,2)),
                CAST(:str_km AS NUMERIC(10,2)),
                CAST(:str_req AS JSON),
                CAST(:str_vehicles AS JSON)
            )
            """
        ).bindparams(
            std_base=8.00, std_km=2.20,
            std_req='["Valid vehicle registration", "Clean driving record", "Vehicle inspection passed"]',
            std_vehicles='["Toyota Camry", "Honda Civic", "Hyundai Elantra", "Nissan Altima"]',
            wav_base=12.00, wav_km=2.80,
            wav_req='["WAV ramp or lift installed", "Wheelchair securement system", "ADA compliance certification", "Accessible vehicle inspection"]',
            wav_vehicles='["Dodge Grand Caravan BraunAbility", "Toyota Sienna Access", "Chrysler Pacifica WAV"]',
            ast_base=14.00, ast_km=3.00,
            ast_req='["First aid certification", "Patient handling training", "Assist equipment on board", "Enhanced insurance coverage"]',
            ast_vehicles='["Ford Transit Custom", "Mercedes Sprinter", "Ram ProMaster"]',
            str_base=22.00, str_km=4.50,
            str_req='["Stretcher mount system", "Medical-grade suspension", "Oxygen supply hookup", "Emergency equipment", "Paramedic-level certification"]',
            str_vehicles='["Ford E-Series Ambulette", "Chevrolet Express Stretcher Van", "Mercedes Sprinter Medical"]',
        )
    )


def downgrade() -> None:
    op.drop_table("vehicle_category_configs")
    op.drop_table("vehicle_documents")

    op.drop_column("vehicle_maintenance_logs", "technician_notes")
    op.drop_column("vehicle_maintenance_logs", "service_type")

    op.drop_column("vehicles", "internal_notes")
    op.drop_column("vehicles", "last_inspection_date")
    op.drop_column("vehicles", "registration_authority")
    op.drop_column("vehicles", "insurance_provider")
    op.drop_column("vehicles", "special_equipment")
    op.drop_column("vehicles", "passenger_capacity")
