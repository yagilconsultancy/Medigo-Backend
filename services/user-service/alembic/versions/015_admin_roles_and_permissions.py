"""admin roles and permissions

Revision ID: 015
Revises: 014
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Create admin_roles table ---
    op.create_table(
        "admin_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default="false"),
        sa.Column("sort_order", sa.Integer(), server_default="999"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # --- Create admin_role_assignments table ---
    op.create_table(
        "admin_role_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("admin_roles.id"), nullable=False, index=True),
        sa.Column("assigned_by", UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Unique constraint to prevent duplicate role assignments
    op.create_unique_constraint(
        "uq_user_role_assignment",
        "admin_role_assignments",
        ["user_id", "role_id"],
    )

    # --- Create module_permissions table ---
    op.create_table(
        "module_permissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("admin_roles.id"), nullable=False, index=True),
        sa.Column("module_name", sa.String(100), nullable=False),
        sa.Column("can_access", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Unique constraint to prevent duplicate module permissions
    op.create_unique_constraint(
        "uq_role_module_permission",
        "module_permissions",
        ["role_id", "module_name"],
    )

    # --- Seed default admin roles ---
    # 1. Super Admin (full access)
    op.execute(
        sa.text(
            """
        INSERT INTO admin_roles (id, name, display_name, description, color, is_system, sort_order, created_at)
        VALUES (
            gen_random_uuid(),
            :name,
            :display_name,
            :description,
            :color,
            true,
            1,
            now()
        )
        """
        ).bindparams(
            name="super_admin",
            display_name="Super Admin",
            description="Full system access with all permissions",
            color="#8B5CF6",
        )
    )

    # 2. Operations Manager
    op.execute(
        sa.text(
            """
        INSERT INTO admin_roles (id, name, display_name, description, color, is_system, sort_order, created_at)
        VALUES (
            gen_random_uuid(),
            :name,
            :display_name,
            :description,
            :color,
            true,
            2,
            now()
        )
        """
        ).bindparams(
            name="operations_manager",
            display_name="Operations Manager",
            description="Manage bookings, dispatch, tracking, and fleet operations",
            color="#3B82F6",
        )
    )

    # 3. Finance Manager
    op.execute(
        sa.text(
            """
        INSERT INTO admin_roles (id, name, display_name, description, color, is_system, sort_order, created_at)
        VALUES (
            gen_random_uuid(),
            :name,
            :display_name,
            :description,
            :color,
            true,
            3,
            now()
        )
        """
        ).bindparams(
            name="finance_manager",
            display_name="Finance Manager",
            description="Manage payments, invoices, and financial analytics",
            color="#10B981",
        )
    )

    # 4. Support Admin
    op.execute(
        sa.text(
            """
        INSERT INTO admin_roles (id, name, display_name, description, color, is_system, sort_order, created_at)
        VALUES (
            gen_random_uuid(),
            :name,
            :display_name,
            :description,
            :color,
            true,
            4,
            now()
        )
        """
        ).bindparams(
            name="support_admin",
            display_name="Support Admin",
            description="Handle customer support, notifications, and rider issues",
            color="#F59E0B",
        )
    )

    # --- Seed module permissions for each role ---
    # All 16 modules from admin_role_service.py
    modules = [
        "analytics_dashboard",
        "booking_management",
        "dispatch_center",
        "gps_tracking",
        "fleet_management",
        "driver_management",
        "vehicle_management",
        "rider_management",
        "payments_finance",
        "invoices_billing",
        "safety_incidents",
        "notifications",
        "support_center",
        "dashboard_settings",
        "roles_permissions",
        "system_logs",
    ]

    # Super Admin - access to all modules
    for module in modules:
        op.execute(
            sa.text(
                """
            INSERT INTO module_permissions (id, role_id, module_name, can_access, created_at)
            SELECT gen_random_uuid(), id, :module_name, true, now()
            FROM admin_roles WHERE name = 'super_admin'
            """
            ).bindparams(module_name=module)
        )

    # Operations Manager - core operations modules
    ops_modules = [
        "analytics_dashboard",
        "booking_management",
        "dispatch_center",
        "gps_tracking",
        "fleet_management",
        "driver_management",
        "vehicle_management",
        "safety_incidents",
    ]
    for module in ops_modules:
        op.execute(
            sa.text(
                """
            INSERT INTO module_permissions (id, role_id, module_name, can_access, created_at)
            SELECT gen_random_uuid(), id, :module_name, true, now()
            FROM admin_roles WHERE name = 'operations_manager'
            """
            ).bindparams(module_name=module)
        )

    # Finance Manager - finance modules
    finance_modules = [
        "analytics_dashboard",
        "payments_finance",
        "invoices_billing",
        "driver_management",  # for payouts
        "rider_management",  # for billing
    ]
    for module in finance_modules:
        op.execute(
            sa.text(
                """
            INSERT INTO module_permissions (id, role_id, module_name, can_access, created_at)
            SELECT gen_random_uuid(), id, :module_name, true, now()
            FROM admin_roles WHERE name = 'finance_manager'
            """
            ).bindparams(module_name=module)
        )

    # Support Admin - support modules
    support_modules = [
        "support_center",
        "notifications",
        "rider_management",
        "booking_management",  # view bookings for support
        "gps_tracking",  # track rides for support
    ]
    for module in support_modules:
        op.execute(
            sa.text(
                """
            INSERT INTO module_permissions (id, role_id, module_name, can_access, created_at)
            SELECT gen_random_uuid(), id, :module_name, true, now()
            FROM admin_roles WHERE name = 'support_admin'
            """
            ).bindparams(module_name=module)
        )


def downgrade() -> None:
    op.drop_constraint("uq_role_module_permission", "module_permissions", type_="unique")
    op.drop_table("module_permissions")
    op.drop_constraint("uq_user_role_assignment", "admin_role_assignments", type_="unique")
    op.drop_table("admin_role_assignments")
    op.drop_table("admin_roles")
