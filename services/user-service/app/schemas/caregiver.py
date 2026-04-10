from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CaregiverCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    email: EmailStr
    phone: str = Field(..., max_length=20)
    specialty: str = Field(...)  # PSW, RPN, RN, HCA, Paramedic, OT, PT
    city: str | None = Field(None, max_length=100)
    province: str | None = Field(None, max_length=50)
    capabilities: list[str] | None = None  # service_capabilities JSONB
    fleet_id: UUID | None = None


class CaregiverUpdate(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    specialty: str | None = None
    city: str | None = Field(None, max_length=100)
    province: str | None = Field(None, max_length=50)
    capabilities: list[str] | None = None
    fleet_id: UUID | None = None


class CaregiverKPIs(BaseModel):
    total_caregivers: int
    available_now: int
    on_assignment: int
    avg_rating: float


class CaregiverRosterRow(BaseModel):
    caregiver_id: UUID
    caregiver_profile_id: UUID
    full_name: str
    avatar_url: str | None = None
    specialty: str
    certifications: list[str] = []
    capabilities: list[str] = []
    status: str  # available, on_assignment
    rating: float | None = None
    assignments: int = 0
    location: str | None = None
    account_status: str


class CaregiverProfileCard(BaseModel):
    caregiver_id: UUID
    caregiver_profile_id: UUID
    full_name: str
    avatar_url: str | None = None
    specialty: str
    phone: str | None = None
    location: str | None = None
    capabilities: list[str] = []
    rating: float | None = None
    assignments: int = 0
    joined: datetime


class CaregiverPersonalInfo(BaseModel):
    full_name: str
    phone: str | None = None
    email: str | None = None
    specialty: str
    city: str | None = None
    province: str | None = None
    joined: datetime
    languages: list[str] = []
    capabilities: list[str] = []


class CaregiverCertification(BaseModel):
    name: str
    status: str  # active, expired, pending
    expiry_date: str | None = None


class CaregiverAssignment(BaseModel):
    assignment_id: str
    patient_name: str
    route: str
    date: str
    duration: str
    status: str


class CaregiverRating(BaseModel):
    patient_name: str
    rating: int
    review: str | None = None
    date: str


class CaregiverDetailResponse(BaseModel):
    caregiver_id: UUID
    caregiver_profile_id: UUID
    personal_info: CaregiverPersonalInfo
    certifications: list[CaregiverCertification] = []
    assignments: list[CaregiverAssignment] = []
    ratings: list[CaregiverRating] = []
    total_assignments: int = 0
    avg_rating: float | None = None
