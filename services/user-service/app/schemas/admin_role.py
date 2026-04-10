from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Request schemas
class AdminRoleCreate(BaseModel):
    name: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=20)


class AdminRoleUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=255)
    color: str | None = Field(None, max_length=20)


class AssignRoleRequest(BaseModel):
    user_id: UUID
    role_id: UUID


class ModulePermissionUpdate(BaseModel):
    role_id: UUID
    module_name: str
    can_access: bool


# Response schemas
class AdminRoleResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    description: str | None = None
    color: str | None = None
    is_system: bool
    admin_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminRoleDetailResponse(AdminRoleResponse):
    admins: list[dict] = []  # {user_id, full_name, email, last_active, joined}


class ModulePermissionResponse(BaseModel):
    id: UUID
    role_id: UUID
    module_name: str
    can_access: bool

    model_config = {"from_attributes": True}


class PermissionMatrixRow(BaseModel):
    module_name: str
    module_display_name: str
    category: str  # CORE, PEOPLE, FINANCE, SAFETY, SERVICE, ADMINISTRATION


class PermissionMatrixResponse(BaseModel):
    roles: list[AdminRoleResponse]
    modules: list[PermissionMatrixRow]
    permissions: dict[str, dict[str, bool]]  # {role_id: {module_name: can_access}}


class AdminRoleCardResponse(BaseModel):
    id: UUID
    name: str
    display_name: str
    color: str | None = None
    admin_count: int = 0
    total_modules: int = 0

    model_config = {"from_attributes": True}
