from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admin_role import AdminRole, AdminRoleAssignment, ModulePermission


class AdminRoleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, role: AdminRole) -> AdminRole:
        self.session.add(role)
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def get_by_id(self, role_id: UUID) -> AdminRole | None:
        result = await self.session.execute(
            select(AdminRole)
            .where(AdminRole.id == role_id)
            .options(selectinload(AdminRole.assignments), selectinload(AdminRole.permissions))
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> AdminRole | None:
        result = await self.session.execute(
            select(AdminRole).where(AdminRole.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[AdminRole]:
        result = await self.session.execute(
            select(AdminRole)
            .options(selectinload(AdminRole.assignments))
            .order_by(AdminRole.sort_order, AdminRole.name)
        )
        return list(result.scalars().all())

    async def update(self, role: AdminRole) -> AdminRole:
        await self.session.flush()
        await self.session.refresh(role)
        return role

    async def delete(self, role_id: UUID) -> None:
        role = await self.get_by_id(role_id)
        if role and not role.is_system:
            await self.session.delete(role)
            await self.session.flush()

    async def assign_role(self, assignment: AdminRoleAssignment) -> AdminRoleAssignment:
        self.session.add(assignment)
        await self.session.flush()
        await self.session.refresh(assignment)
        return assignment

    async def remove_role_assignment(self, user_id: UUID, role_id: UUID) -> None:
        result = await self.session.execute(
            select(AdminRoleAssignment).where(
                AdminRoleAssignment.user_id == user_id,
                AdminRoleAssignment.role_id == role_id,
            )
        )
        assignment = result.scalar_one_or_none()
        if assignment:
            await self.session.delete(assignment)
            await self.session.flush()

    async def get_user_roles(self, user_id: UUID) -> list[AdminRole]:
        result = await self.session.execute(
            select(AdminRole)
            .join(AdminRoleAssignment)
            .where(AdminRoleAssignment.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_role_users_count(self, role_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(AdminRoleAssignment.role_id == role_id)
        )
        return result.scalar_one()

    # Module permissions
    async def set_module_permission(
        self, role_id: UUID, module_name: str, can_access: bool
    ) -> ModulePermission:
        # Check if exists
        result = await self.session.execute(
            select(ModulePermission).where(
                ModulePermission.role_id == role_id,
                ModulePermission.module_name == module_name,
            )
        )
        perm = result.scalar_one_or_none()

        if perm:
            perm.can_access = can_access
            await self.session.flush()
            await self.session.refresh(perm)
        else:
            perm = ModulePermission(
                role_id=role_id, module_name=module_name, can_access=can_access
            )
            self.session.add(perm)
            await self.session.flush()
            await self.session.refresh(perm)

        return perm

    async def get_role_permissions(self, role_id: UUID) -> list[ModulePermission]:
        result = await self.session.execute(
            select(ModulePermission).where(ModulePermission.role_id == role_id)
        )
        return list(result.scalars().all())

    async def get_all_permissions(self) -> list[ModulePermission]:
        result = await self.session.execute(select(ModulePermission))
        return list(result.scalars().all())
