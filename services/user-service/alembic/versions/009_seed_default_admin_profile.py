"""Seed default admin user profile

Revision ID: 009
Revises: 008
Create Date: 2026-03-23
"""
import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO users (id, email, first_name, last_name, role, is_active, onboarding_step, onboarding_completed)
            VALUES (
                CAST(:id AS UUID),
                :email,
                :first_name,
                :last_name,
                'admin',
                true,
                1,
                true
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(
            id=ADMIN_ID,
            email="admin@medigo.ca",
            first_name="MediGo",
            last_name="Admin",
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM users WHERE id = CAST(:id AS UUID)"
        ).bindparams(id=ADMIN_ID)
    )
