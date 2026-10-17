"""Widen otp_records.code so it can hold a hashed code.

New codes are stored as a keyed hash (about 67 characters). Existing rows keep
their plain 6 digit code and are still accepted until they expire.

Revision ID: 009
Revises: 008
"""

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "otp_records",
        "code",
        existing_type=sa.String(6),
        type_=sa.String(80),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Hashed rows cannot fit in 6 characters; drop them first (codes are
    # short lived, users simply request a new one).
    op.execute("DELETE FROM otp_records WHERE length(code) > 6")
    op.alter_column(
        "otp_records",
        "code",
        existing_type=sa.String(80),
        type_=sa.String(6),
        existing_nullable=False,
    )
