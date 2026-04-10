from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.admin_role_repo import AdminRoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.admin_role import (
    AdminRoleCardResponse,
    AdminRoleCreate,
    AdminRoleDetailResponse,
    AdminRoleUpdate,
    AssignRoleRequest,
    ModulePermissionUpdate,
    PermissionMatrixResponse,
    UserPermissionsResponse,
)
from app.services.admin_role_service import AdminRoleService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> AdminRoleService:
    return AdminRoleService(
        role_repo=AdminRoleRepository(session),
        user_repo=UserRepository(session),
    )


# Admin Roles endpoints
@router.get(
    "/admin/roles",
    response_model=StandardResponse[list[AdminRoleCardResponse]],
)
async def list_admin_roles(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """List all admin roles with counts."""
    roles = await service.list_roles()
    return StandardResponse(data=roles)


@router.post(
    "/admin/roles",
    response_model=StandardResponse[dict],
    status_code=201,
)
async def create_admin_role(
    body: AdminRoleCreate,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Create a new admin role."""
    try:
        role = await service.create_role(
            name=body.name,
            display_name=body.display_name,
            description=body.description,
            color=body.color,
        )
        return StandardResponse(
            data={"role_id": str(role.id), "name": role.name},
            message="Role created successfully",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/admin/roles/{role_id}",
    response_model=StandardResponse[AdminRoleDetailResponse],
)
async def get_admin_role_detail(
    role_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Get role details with assigned admins."""
    try:
        role_detail = await service.get_role_detail(role_id)
        return StandardResponse(data=role_detail)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put(
    "/admin/roles/{role_id}",
    response_model=StandardResponse[dict],
)
async def update_admin_role(
    role_id: UUID,
    body: AdminRoleUpdate,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Update role information."""
    try:
        role = await service.update_role(
            role_id=role_id,
            display_name=body.display_name,
            description=body.description,
            color=body.color,
        )
        return StandardResponse(
            data={"role_id": str(role.id)}, message="Role updated successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/admin/roles/{role_id}",
    response_model=StandardResponse,
)
async def delete_admin_role(
    role_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Delete an admin role."""
    try:
        await service.delete_role(role_id)
        return StandardResponse(message="Role deleted successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/admin/roles/assign",
    response_model=StandardResponse[dict],
)
async def assign_role_to_admin(
    body: AssignRoleRequest,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Assign a role to an admin user."""
    try:
        await service.assign_role_to_user(
            user_id=body.user_id,
            role_id=body.role_id,
            admin_id=admin.id,
        )
        return StandardResponse(message="Role assigned successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/admin/roles/remove",
    response_model=StandardResponse,
)
async def remove_role_from_admin(
    body: AssignRoleRequest,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Remove a role from an admin user."""
    await service.remove_role_from_user(user_id=body.user_id, role_id=body.role_id)
    return StandardResponse(message="Role removed successfully")


# Permission Control endpoints
@router.get(
    "/admin/permissions/matrix",
    response_model=StandardResponse[PermissionMatrixResponse],
)
async def get_permission_matrix(
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Get the complete permission matrix."""
    matrix = await service.get_permission_matrix()
    return StandardResponse(data=matrix)


@router.post(
    "/admin/permissions/save",
    response_model=StandardResponse,
)
async def save_permissions(
    permissions: list[ModulePermissionUpdate],
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Bulk save module permissions."""
    perm_list = [
        {
            "role_id": str(p.role_id),
            "module_name": p.module_name,
            "can_access": p.can_access,
        }
        for p in permissions
    ]
    await service.save_permissions(perm_list)
    return StandardResponse(message="Permissions saved successfully")


@router.get(
    "/admin/me/permissions",
    response_model=StandardResponse[UserPermissionsResponse],
)
async def get_my_permissions(
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRoleService = Depends(_get_service),
):
    """Get current user's roles and accessible modules."""
    try:
        permissions = await service.get_user_permissions(admin.id)
        return StandardResponse(data=permissions)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
