"""Seed default admin user

Revision ID: 004
Revises: 003
Create Date: 2026-03-23
"""
import uuid

import sqlalchemy as sa
from alembic import op
from argon2 import PasswordHasher

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_EMAIL = "admin@medigo.ca"
ADMIN_PASSWORD = "Admin@1234"


def upgrade() -> None:
    hasher = PasswordHasher()
    password_hash = hasher.hash(ADMIN_PASSWORD)

    op.execute(
        sa.text(
            """
            INSERT INTO user_credentials (id, email, password_hash, role, is_verified, is_active, failed_attempts)
            VALUES (
                CAST(:id AS UUID),
                :email,
                :password_hash,
                'admin',
                true,
                true,
                0
            )
            ON CONFLICT (email) DO NOTHING
            """
        ).bindparams(
            id=ADMIN_ID,
            email=ADMIN_EMAIL,
            password_hash=password_hash,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM user_credentials WHERE id = CAST(:id AS UUID)"
        ).bindparams(id=ADMIN_ID)
    )
