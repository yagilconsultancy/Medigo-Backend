from datetime import date
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserProfileResponse(BaseModel):
    id: UUID
    email: str | None = None
    phone: str | None = None
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    gender: str | None = None
    avatar_url: str | None = None
    role: str
    business_id: UUID | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=20)
    avatar_url: str | None = Field(None, max_length=500)


class EmergencyContactCreate(BaseModel):
    name: str = Field(..., max_length=200)
    phone: str = Field(..., max_length=20)
    relationship_type: str | None = Field(None, max_length=50)
    is_primary: bool = False


class EmergencyContactResponse(BaseModel):
    id: UUID
    name: str
    phone: str
    relationship_type: str | None = None
    is_primary: bool

    model_config = {"from_attributes": True}


class PassengerCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    date_of_birth: date | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    medical_notes: str | None = None
    is_self: bool = False


class PassengerUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    medical_notes: str | None = None


class PassengerResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    mobility_level: str | None = None
    assistance_level: str | None = None
    medical_notes: str | None = None
    is_self: bool

    model_config = {"from_attributes": True}
