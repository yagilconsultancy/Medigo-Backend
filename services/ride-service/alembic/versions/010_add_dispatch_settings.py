"""Add dispatch_settings table for auto-dispatch configuration.

Revision ID: 010
Revises: 009
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dispatch_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "auto_dispatch_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("search_radius_km", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "priority_rules",
            JSONB,
            nullable=False,
            server_default='{"prioritize_by_rating": true, "prioritize_by_fleet": false, "match_vehicle_type": true}',
        ),
        sa.Column(
            "fallback_behavior",
            JSONB,
            nullable=False,
            server_default='{"expand_search_radius": true, "notify_dispatch_team": false, "notify_rider": false}',
        ),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Insert default settings record
    op.execute(
        sa.text(
            """
            INSERT INTO dispatch_settings (id, auto_dispatch_enabled, search_radius_km)
            VALUES (gen_random_uuid(), false, 5)
            """
        )
    )


def downgrade() -> None:
    op.drop_table("dispatch_settings")
