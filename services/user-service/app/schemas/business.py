from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class BusinessCreate(BaseModel):
    name: str = Field(..., max_length=255)
    type: str | None = Field(None, max_length=50)
    tax_id: str | None = Field(None, max_length=50)
    address: str | None = None
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=50)
    zip_code: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=20)
    email: str | None = None


class BusinessUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    type: str | None = Field(None, max_length=50)
    address: str | None = None
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=50)
    zip_code: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=20)
    email: str | None = None


class BusinessResponse(BaseModel):
    id: UUID
    name: str
    type: str | None = None
    tax_id: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    email: str | None = None
    logo_url: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class InviteDriverRequest(BaseModel):
    email: str


class InvitationResponse(BaseModel):
    id: UUID
    business_id: UUID
    email: str
    status: str
    expires_at: str

    model_config = {"from_attributes": True}
