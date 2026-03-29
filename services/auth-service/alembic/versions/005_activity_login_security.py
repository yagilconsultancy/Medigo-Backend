"""Activity logs, login records, and security settings

Revision ID: 005
Revises: 004
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Sequence ──
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS activity_log_seq START WITH 1"))

    # ── activity_logs table ──
    op.create_table(
        "activity_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("log_number", sa.Integer(), nullable=False),
        sa.Column("admin_id", UUID(as_uuid=True), nullable=False),
        sa.Column("admin_name", sa.String(200), nullable=False),
        sa.Column("admin_email", sa.String(255), nullable=False),
        sa.Column("action_title", sa.String(255), nullable=False),
        sa.Column("action_description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("target_entity_id", sa.String(100), nullable=True),
        sa.Column("target_entity_type", sa.String(50), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activity_logs_log_number", "activity_logs", ["log_number"])
    op.create_index("ix_activity_logs_admin_id", "activity_logs", ["admin_id"])
    op.create_index("ix_activity_logs_category", "activity_logs", ["category"])
    op.create_index("ix_activity_logs_severity", "activity_logs", ["severity"])
    op.create_index("ix_activity_logs_created_at", "activity_logs", ["created_at"])

    # ── login_records table ──
    op.create_table(
        "login_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("admin_name", sa.String(200), nullable=False),
        sa.Column("admin_email", sa.String(255), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("device_info", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("is_suspicious", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_login_records_user_id", "login_records", ["user_id"])
    op.create_index("ix_login_records_success", "login_records", ["success"])
    op.create_index("ix_login_records_created_at", "login_records", ["created_at"])

    # ── security_settings table (singleton) ──
    op.create_table(
        "security_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("two_factor_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("ip_geo_blocking_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("ip_whitelist_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("audit_logging_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("session_timeout_hours", sa.Integer(), server_default=sa.text("4")),
        sa.Column("min_password_length", sa.Integer(), server_default=sa.text("12")),
        sa.Column("require_uppercase", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("require_lowercase", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("require_numbers", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("require_special_chars", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("whitelisted_ips", JSONB, nullable=True),
        sa.Column("two_fa_enabled_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("total_admin_count", sa.Integer(), server_default=sa.text("8")),
        sa.Column("threats_blocked", sa.Integer(), server_default=sa.text("0")),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("is_active", name="uq_security_settings_is_active"),
    )

    # Seed default security settings row
    op.execute(sa.text(
        "INSERT INTO security_settings (is_active, two_factor_enabled, ip_geo_blocking_enabled, "
        "ip_whitelist_enabled, audit_logging_enabled, session_timeout_hours, min_password_length, "
        "require_uppercase, require_lowercase, require_numbers, require_special_chars, "
        "two_fa_enabled_count, total_admin_count, threats_blocked) "
        "VALUES (true, false, false, false, true, 4, 12, true, true, true, true, 8, 8, 14)"
    ))


def downgrade() -> None:
    op.drop_table("security_settings")
    op.drop_table("login_records")
    op.drop_table("activity_logs")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS activity_log_seq"))
