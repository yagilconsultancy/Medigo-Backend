from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


# --- KPIs ---

class AdminDriverKPIs(BaseModel):
    total_drivers: int
    active_count: int
    suspended_count: int
    pending_count: int
    online_count: int
    available_now: int = 0
    on_trip: int = 0
    total_mileage: float = 0.0
    approval_rate: float


# --- List Items ---

class AdminDriverListItem(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    fleet_id: UUID | None = None
    fleet_name: str | None = None
    account_status: str
    is_online: bool
    is_approved: bool
    rating: float
    total_trips: int
    vehicle_type: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_plate: str | None = None
    specialty: str | None = None
    document_status: str = "unknown"
    created_at: datetime | None = None


class AdminDriverListResponse(BaseModel):
    kpis: AdminDriverKPIs
    drivers: list[AdminDriverListItem]
    total: int
    page: int
    limit: int
    total_pages: int


# --- Driver Detail ---

class AdminDriverTripStats(BaseModel):
    total_trips: int = 0
    hours_online: float = 0.0
    average_earnings: float = 0.0


class AdminDriverRatingItem(BaseModel):
    ride_id: UUID
    rated_by_user_id: UUID | None = None
    rating: int
    comment: str | None = None
    created_at: datetime | None = None


class DriverDocumentSummary(BaseModel):
    id: UUID
    document_type: str
    file_name: str
    verification_status: str
    expires_at: date | None = None
    created_at: datetime | None = None


class SuspensionLogItem(BaseModel):
    id: UUID
    action: str
    reason: str | None = None
    performed_by: UUID
    created_at: datetime | None = None


class AdminDriverDetailResponse(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    fleet_id: UUID | None = None
    fleet_name: str | None = None
    account_status: str
    is_online: bool
    is_approved: bool
    rating: float
    total_trips: int
    specialty: str | None = None
    service_capabilities: list[str] = []

    # Vehicle info
    vehicle_type: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_year: int | None = None
    vehicle_plate: str | None = None
    vehicle_color: str | None = None
    vehicle_vin: str | None = None
    vehicle_photo_url: str | None = None

    # License & Certification
    license_number: str | None = None
    license_expiry: date | None = None
    medical_transport_certification: str | None = None

    # Personal
    date_of_birth: date | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    # Status details
    background_check_status: str | None = None
    suspension_reason: str | None = None
    suspended_at: datetime | None = None
    deactivated_at: datetime | None = None
    approved_at: datetime | None = None
    notes: str | None = None
    invited_via_email: str | None = None

    # Enriched data
    trip_stats: AdminDriverTripStats = AdminDriverTripStats()
    documents: list[DriverDocumentSummary] = []
    ratings: list[AdminDriverRatingItem] = []
    suspension_history: list[SuspensionLogItem] = []

    # Invitation (populated on create only)
    invite_token: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Create / Update ---

class CreateDriverRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    fleet_id: UUID
    license_number: str | None = None
    license_expiry: date | None = None
    medical_transport_certification: str | None = None
    background_check_status: str = "pending"
    vehicle_id: UUID | None = None
    service_capabilities: list[str] = []
    specialty: str | None = None
    date_of_birth: date | None = None
    account_status: str = "pending"
    is_approved: bool = False


class UpdateDriverRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    fleet_id: UUID | None = None
    license_number: str | None = None
    license_expiry: date | None = None
    medical_transport_certification: str | None = None
    background_check_status: str | None = None
    vehicle_id: UUID | None = None
    service_capabilities: list[str] | None = None
    specialty: str | None = None
    date_of_birth: date | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    address: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    account_status: str | None = None
    notes: str | None = None


# --- Actions ---

class SuspendDriverRequest(BaseModel):
    reason: str


class ReassignFleetRequest(BaseModel):
    fleet_id: UUID


# --- Document Overview ---

class AdminDriverDocumentKPIs(BaseModel):
    total_drivers: int
    all_docs_verified: int
    pending_review: int
    expired_docs: int


class AdminDriverDocumentListItem(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    fleet_name: str | None = None
    documents: list[DriverDocumentSummary]
    document_status: str


class AdminDriverDocumentOverview(BaseModel):
    kpis: AdminDriverDocumentKPIs
    drivers: list[AdminDriverDocumentListItem]
    total: int
    page: int
    limit: int
    total_pages: int


# --- Status Overview ---

class DriverStatusKPIs(BaseModel):
    active_count: int
    suspended_count: int
    pending_count: int
    deactivated_count: int


class DriverStatusItem(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    fleet_name: str | None = None
    account_status: str
    suspension_reason: str | None = None
    suspended_at: datetime | None = None
    created_at: datetime | None = None


class DriverStatusSection(BaseModel):
    status: str
    count: int
    drivers: list[DriverStatusItem]


class AdminDriverStatusOverview(BaseModel):
    kpis: DriverStatusKPIs
    sections: list[DriverStatusSection]
