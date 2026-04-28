from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    id: UUID
    email: str | None = None
    phone: str | None = None
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    gender: str | None = None
    avatar_url: str | None = None
    home_address: str | None = None
    medical_notes: str | None = None
    role: str
    business_id: UUID | None = None
    is_active: bool
    is_guest: bool = False
    consent_emergency_services: bool = False
    consent_privacy_policy: bool = False
    consent_terms_of_service: bool = False
    consent_data_location: bool = False
    consent_accepted_at: datetime | None = None
    onboarding_step: int = 1
    onboarding_completed: bool = False

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    date_of_birth: date | None = None
    gender: str | None = Field(None, max_length=20)
    avatar_url: str | None = Field(None, max_length=500)
    home_address: str | None = Field(None, max_length=500)
    medical_notes: str | None = None


class UpdateConsentRequest(BaseModel):
    consent_emergency_services: bool = False
    consent_privacy_policy: bool = False
    consent_terms_of_service: bool = False
    consent_data_location: bool = False


class ConsentResponse(BaseModel):
    consent_emergency_services: bool
    consent_privacy_policy: bool
    consent_terms_of_service: bool
    consent_data_location: bool
    consent_accepted_at: datetime | None = None

    model_config = {"from_attributes": True}


class OnboardingStatusResponse(BaseModel):
    current_step: int
    total_steps: int = 5
    completed: bool
    steps: list[dict]

    model_config = {"from_attributes": True}


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
