"""Add configurable lockout threshold; clear fake seeded KPI counters.

Migration 005 seeded the security_settings singleton with invented KPI values
(total_admin_count=8, two_fa_enabled_count=8, threats_blocked=14) that nothing
ever recomputed, so the Security Settings cards showed fiction. Those figures
are now derived from real data at read time, so the stored counters are zeroed
to make sure a stale value can never surface again.

Also promotes max_failed_login_attempts from a hardcoded env constant to a
per-deployment setting -- the BackOffice already renders the field, previously
as a read-only fake.

Revision ID: 006
Revises: 005
"""

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "security_settings",
        sa.Column(
            "max_failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("5"),
        ),
    )

    # The KPI endpoint now computes these; stop serving the seeded fiction.
    op.execute(
        sa.text(
            "UPDATE security_settings SET "
            "two_fa_enabled_count = 0, total_admin_count = 0, threats_blocked = 0"
        )
    )


def downgrade() -> None:
    op.drop_column("security_settings", "max_failed_login_attempts")
