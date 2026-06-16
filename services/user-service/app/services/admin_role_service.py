import logging
from uuid import UUID

from app.models.admin_role import AdminRole, AdminRoleAssignment
from app.repositories.admin_role_repo import AdminRoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.admin_role import (
    AdminRoleCardResponse,
    AdminRoleDetailResponse,
    AdminRoleResponse,
    PermissionMatrixResponse,
    PermissionMatrixRow,
)

logger = logging.getLogger(__name__)

# Module definitions
MODULES = [
    {"name": "analytics_dashboard", "display_name": "Analytics Dashboard", "category": "CORE"},
    {"name": "booking_management", "display_name": "Booking Management", "category": "CORE"},
    {"name": "dispatch_center", "display_name": "Dispatch Center", "category": "CORE"},
    {"name": "gps_tracking", "display_name": "GPS Tracking", "category": "CORE"},
    {"name": "fleet_management", "display_name": "Fleet Management", "category": "PEOPLE"},
    {"name": "driver_management", "display_name": "Driver Management", "category": "PEOPLE"},
    {"name": "vehicle_management", "display_name": "Vehicle Management", "category": "PEOPLE"},
    {"name": "rider_management", "display_name": "Rider Management", "category": "PEOPLE"},
    {"name": "payments_finance", "display_name": "Payments & Finance", "category": "FINANCE"},
    {"name": "invoices_billing", "display_name": "Invoices & Billing", "category": "FINANCE"},
    {"name": "safety_incidents", "display_name": "Safety & Incidents", "category": "SAFETY"},
    {"name": "notifications", "display_name": "Notifications", "category": "SAFETY"},
    {"name": "support_center", "display_name": "Support Center", "category": "SERVICE"},
    {"name": "dashboard_settings", "display_name": "Dashboard Settings", "category": "ADMINISTRATION"},
    {"name": "roles_permissions", "display_name": "Roles & Permissions", "category": "ADMINISTRATION"},
    {"name": "system_logs", "display_name": "System Logs", "category": "ADMINISTRATION"},
]


class AdminRoleService:
    def __init__(self, role_repo: AdminRoleRepository, user_repo: UserRepository):
        self.role_repo = role_repo
        self.user_repo = user_repo

    async def list_roles(self) -> list[AdminRoleCardResponse]:
        """Get role cards for Admin Roles tab."""
        roles = await self.role_repo.get_all()

        cards = []
        for role in roles:
            admin_count = len(role.assignments) if role.assignments else 0
            permissions = await self.role_repo.get_role_permissions(role.id)

            cards.append(
                AdminRoleCardResponse(
                    id=role.id,
                    name=role.name,
                    display_name=role.display_name,
                    color=role.color,
                    admin_count=admin_count,
                    total_modules=len(permissions),
                )
            )

        return cards

    async def get_role_detail(self, role_id: UUID) -> AdminRoleDetailResponse:
        """Get role detail with assigned admins."""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise ValueError("Role not found")

        admin_count = len(role.assignments) if role.assignments else 0

        # Get admin details
        admins = []
        if role.assignments:
            for assignment in role.assignments:
                user = await self.user_repo.get_by_id(assignment.user_id)
                if user:
                    admins.append({
                        "user_id": str(user.id),
                        "full_name": f"{user.first_name} {user.last_name}",
                        "email": user.email,
                        "last_active": "Today",  # TODO: Implement last active tracking
                        "joined": assignment.assigned_at.strftime("%b %d, %Y"),
                    })

        return AdminRoleDetailResponse(
            id=role.id,
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            color=role.color,
            is_system=role.is_system,
            admin_count=admin_count,
            created_at=role.created_at,
            admins=admins,
        )

    async def create_role(
        self,
        name: str,
        display_name: str,
        description: str | None,
        color: str | None,
    ) -> AdminRole:
        """Create a new admin role."""
        # Check if name already exists
        existing = await self.role_repo.get_by_name(name)
        if existing:
            raise ValueError(f"Role with name '{name}' already exists")

        role = AdminRole(
            name=name,
            display_name=display_name,
            description=description,
            color=color,
        )
        return await self.role_repo.create(role)

    async def update_role(
        self,
        role_id: UUID,
        display_name: str | None,
        description: str | None,
        color: str | None,
    ) -> AdminRole:
        """Update role information."""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise ValueError("Role not found")

        if role.is_system:
            raise ValueError("Cannot modify system role")

        if display_name is not None:
            role.display_name = display_name
        if description is not None:
            role.description = description
        if color is not None:
            role.color = color

        return await self.role_repo.update(role)

    async def delete_role(self, role_id: UUID) -> None:
        """Delete a role."""
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise ValueError("Role not found")

        if role.is_system:
            raise ValueError("Cannot delete system role")

        await self.role_repo.delete(role_id)

    async def assign_role_to_user(
        self, user_id: UUID, role_id: UUID, admin_id: UUID
    ) -> AdminRoleAssignment:
        """Assign a role to a user."""
        # Verify role exists
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise ValueError("Role not found")

        # Verify user exists
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        assignment = AdminRoleAssignment(
            user_id=user_id,
            role_id=role_id,
            assigned_by=admin_id,
        )
        return await self.role_repo.assign_role(assignment)

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> None:
        """Remove a role from a user."""
        await self.role_repo.remove_role_assignment(user_id, role_id)

    async def get_permission_matrix(self) -> PermissionMatrixResponse:
        """Get the complete permission matrix for all roles and modules."""
        roles = await self.role_repo.get_all()
        all_permissions = await self.role_repo.get_all_permissions()

        # Build permission map
        perm_map: dict[str, dict[str, bool]] = {}
        for perm in all_permissions:
            role_id_str = str(perm.role_id)
            if role_id_str not in perm_map:
                perm_map[role_id_str] = {}
            perm_map[role_id_str][perm.module_name] = perm.can_access

        # Build modules list
        modules = [
            PermissionMatrixRow(
                module_name=m["name"],
                module_display_name=m["display_name"],
                category=m["category"],
            )
            for m in MODULES
        ]

        # Build role responses
        role_responses = []
        for role in roles:
            admin_count = len(role.assignments) if role.assignments else 0
            role_responses.append(
                AdminRoleResponse(
                    id=role.id,
                    name=role.name,
                    display_name=role.display_name,
                    description=role.description,
                    color=role.color,
                    is_system=role.is_system,
                    admin_count=admin_count,
                    created_at=role.created_at,
                )
            )

        return PermissionMatrixResponse(
            roles=role_responses,
            modules=modules,
            permissions=perm_map,
        )

    async def save_permissions(
        self, permissions: list[dict]
    ) -> None:
        """Bulk save module permissions."""
        for perm_data in permissions:
            await self.role_repo.set_module_permission(
                role_id=UUID(perm_data["role_id"]),
                module_name=perm_data["module_name"],
                can_access=perm_data["can_access"],
            )

    async def get_user_permissions(self, user_id: UUID) -> dict:
        """Get current user's roles and accessible modules."""
        # Get user info
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        # Get user's role assignments
        user_roles = await self.role_repo.get_user_roles(user_id)

        # Collect all accessible modules from all roles
        accessible_modules = set()
        role_info = []

        for role in user_roles:
            # Get permissions for this role
            permissions = await self.role_repo.get_role_permissions(role.id)

            # Add modules where can_access is True
            for perm in permissions:
                if perm.can_access:
                    accessible_modules.add(perm.module_name)

            role_info.append({
                "id": role.id,
                "name": role.name,
                "display_name": role.display_name,
                "color": role.color,
            })

        return {
            "user": {
                "id": str(user.id),
                "full_name": f"{user.first_name} {user.last_name}",
                "email": user.email,
            },
            "roles": role_info,
            "accessible_modules": sorted(list(accessible_modules)),
        }

    async def check_module_access(self, user_id: UUID, module_name: str) -> bool:
        """Check if user has access to a specific module.

        Admin users with no explicit role assignments get full access
        (backward compatibility for admins created before the role system).
        """
        user_roles = await self.role_repo.get_user_roles(user_id)

        if not user_roles:
            return True

        for role in user_roles:
            permissions = await self.role_repo.get_role_permissions(role.id)
            for perm in permissions:
                if perm.module_name == module_name and perm.can_access:
                    return True

        return False
