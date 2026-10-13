"""Add social_identities for Sign in with Apple / Google.

Each row links one provider identity (provider + the provider's stable user id)
to one MediGo account. A provider identity can belong to only one account.

Revision ID: 008
Revises: 007
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "social_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", "subject", name="uq_social_provider_subject"),
    )
    op.create_index("ix_social_identities_user_id", "social_identities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_social_identities_user_id", table_name="social_identities")
    op.drop_table("social_identities")
