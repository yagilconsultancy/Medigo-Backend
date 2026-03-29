"""Seed default MediGo fleet

Revision ID: 010
Revises: 009
Create Date: 2026-03-28
"""
import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

MEDIGO_FLEET_ID = "00000000-0000-0000-0000-000000000010"
ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO businesses (id, name, type, email, contact_person, is_active, onboarded_by)
            VALUES (
                CAST(:id AS UUID),
                :name,
                :type,
                :email,
                :contact_person,
                true,
                CAST(:onboarded_by AS UUID)
            )
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(
            id=MEDIGO_FLEET_ID,
            name="MediGo",
            type="platform",
            email="admin@medigo.ca",
            contact_person="MediGo Admin",
            onboarded_by=ADMIN_ID,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM businesses WHERE id = CAST(:id AS UUID)"
        ).bindparams(id=MEDIGO_FLEET_ID)
    )
