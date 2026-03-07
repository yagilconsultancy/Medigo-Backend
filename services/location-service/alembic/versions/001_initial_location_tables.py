"""Initial location tables

Revision ID: 001
Revises:
Create Date: 2026-03-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "geocoding_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("address", sa.String(500), nullable=False, index=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("formatted_address", sa.String(500), nullable=False),
        sa.Column("place_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index(
        "ix_geocoding_cache_address_lower",
        "geocoding_cache",
        [sa.text("lower(address)")],
    )

    op.execute("""
        CREATE TABLE service_areas (
            id UUID PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            boundary geometry(POLYGON, 4326) NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    op.execute("""
        CREATE INDEX ix_service_areas_boundary
        ON service_areas USING GIST (boundary)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS service_areas")
    op.drop_index("ix_geocoding_cache_address_lower", table_name="geocoding_cache")
    op.drop_table("geocoding_cache")
    op.execute("DROP EXTENSION IF EXISTS postgis")
