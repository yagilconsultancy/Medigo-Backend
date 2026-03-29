from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


# --- KPIs ---


class AdminRiderKPIs(BaseModel):
    total_riders: int
    active_count: int
    suspended_count: int
    open_tickets: int


# --- List ---


class AdminRiderListItem(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    joined_at: datetime | None = None
    total_trips: int = 0
    total_spent: float = 0.0
    frequency: str = "N/A"
    open_tickets: int = 0
    status: str


class AdminRiderListResponse(BaseModel):
    kpis: AdminRiderKPIs
    riders: list[AdminRiderListItem]
    total: int
    page: int
    limit: int
    total_pages: int


# --- Detail ---


class RiderTripStats(BaseModel):
    total_rides: int = 0
    total_spent: float = 0.0
    avg_cost: float = 0.0


class RiderEmergencyContactInfo(BaseModel):
    name: str
    phone: str
    relationship_type: str | None = None


class RiderPaymentMethodInfo(BaseModel):
    brand: str | None = None
    last_four: str | None = None
    is_default: bool = False


class RiderRideHistoryItem(BaseModel):
    ride_id: UUID
    date: datetime | None = None
    pickup: str | None = None
    destination: str | None = None
    status: str
    fare: float | None = None


class AdminRiderDetailResponse(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    home_address: str | None = None
    medical_notes: str | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None
    status: str
    suspension_reason: str | None = None
    suspended_at: datetime | None = None
    created_at: datetime | None = None
    trip_stats: RiderTripStats = RiderTripStats()
    emergency_contacts: list[RiderEmergencyContactInfo] = []
    payment_methods: list[RiderPaymentMethodInfo] = []


# --- Profiles (card grid) ---


class AdminRiderProfileCard(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    avatar_url: str | None = None
    date_of_birth: date | None = None
    member_since: datetime | None = None
    total_rides: int = 0
    email: str | None = None
    phone: str | None = None
    last_ride: datetime | None = None
    insurance_provider: str | None = None
    insurance_policy_number: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_relationship: str | None = None
    payment_brand: str | None = None
    payment_last_four: str | None = None


# --- Activity ---


class AdminRiderActivityKPIs(BaseModel):
    daily_active_riders: int
    avg_trips_per_week: float
    inactive_30_days: int


class AdminRiderActivityItem(BaseModel):
    user_id: UUID
    first_name: str
    last_name: str
    avatar_url: str | None = None
    last_seen: datetime | None = None
    frequency: str
    avg_trips_per_week: float
    monthly_trips: int
    trend: str
    status: str


class AdminRiderActivityResponse(BaseModel):
    kpis: AdminRiderActivityKPIs
    riders: list[AdminRiderActivityItem]
    total: int
    page: int
    limit: int
    total_pages: int


# --- Issues ---


class RiderIssueKPIs(BaseModel):
    open_count: int
    under_review_count: int
    resolved_count: int


class RiderIssueNoteResponse(BaseModel):
    id: UUID
    author_id: UUID
    note_text: str
    action: str | None = None
    created_at: datetime


class RiderIssueListItem(BaseModel):
    id: UUID
    ticket_number: str
    rider_id: UUID
    rider_name: str
    issue_type: str
    subject: str
    status: str
    priority: str
    created_at: datetime


class RiderIssueDetailResponse(BaseModel):
    id: UUID
    ticket_number: str
    rider_id: UUID
    rider_name: str
    issue_type: str
    subject: str
    description: str
    status: str
    priority: str
    assigned_to: UUID | None = None
    resolved_at: datetime | None = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    notes: list[RiderIssueNoteResponse] = []


class RiderIssueListResponse(BaseModel):
    kpis: RiderIssueKPIs
    issues: list[RiderIssueListItem]
    total: int
    page: int
    limit: int
    total_pages: int


class CreateRiderIssueRequest(BaseModel):
    rider_id: UUID
    issue_type: str
    subject: str
    description: str
    priority: str = "medium"


class UpdateIssueStatusRequest(BaseModel):
    status: str


class AddIssueNoteRequest(BaseModel):
    note_text: str


class SuspendRiderRequest(BaseModel):
    reason: str
