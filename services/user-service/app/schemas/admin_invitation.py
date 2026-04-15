from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# Request schemas
class AdminInviteRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    role_name: str = Field(
        ...,
        description="Admin role name: super_admin, operations_manager, finance_manager, or support_admin",
    )


class RevokeInvitationRequest(BaseModel):
    invitation_id: UUID


# Response schemas
class AdminInvitationResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    role_name: str
    role_display_name: str
    invited_by_name: str
    status: str
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None = None

    model_config = {"from_attributes": True}


class AdminInviteSuccessResponse(BaseModel):
    invitation_id: UUID
    message: str = "Admin invitation sent successfully"
