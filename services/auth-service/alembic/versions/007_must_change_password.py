"""Add must_change_password flag to user credentials.

New admins are created with a one-time random password and must set their own
at first login. Existing rows default to false, so nobody is affected by this
migration.

Revision ID: 007
Revises: 006
"""

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_credentials",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_credentials", "must_change_password")
