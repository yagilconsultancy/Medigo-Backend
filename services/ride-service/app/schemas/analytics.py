from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


# ---- KPI Overview ----

class KPIChange(BaseModel):
    value: float
    change_percent: float
    trend: str  # "up", "down", "flat"


class DashboardKPIs(BaseModel):
    total_trips: KPIChange
    active_drivers: KPIChange
    pending_bookings: KPIChange
    revenue: KPIChange


# ---- Trip Volume Trend ----

class TripVolumePoint(BaseModel):
    date: date
    count: int


class TripVolumeTrendResponse(BaseModel):
    period_days: int
    data: list[TripVolumePoint]
    total: int


# ---- Trip Status Distribution ----

class StatusSlice(BaseModel):
    status: str
    count: int
    percentage: float


class TripStatusDistributionResponse(BaseModel):
    total: int
    distribution: list[StatusSlice]


# ---- Top Performing Drivers ----

class TopDriverEntry(BaseModel):
    rank: int
    driver_id: UUID
    driver_name: str
    avatar_url: str | None = None
    total_trips: int
    average_rating: float


class TopDriversResponse(BaseModel):
    period_days: int
    drivers: list[TopDriverEntry]


# ---- Recent Activity ----

class ActivityEntry(BaseModel):
    id: UUID
    event_type: str
    title: str
    description: str
    ride_id: UUID | None = None
    timestamp: datetime


class RecentActivityResponse(BaseModel):
    activities: list[ActivityEntry]


# ---- Transport Type Distribution ----

class TransportTypeSlice(BaseModel):
    transport_type: str
    count: int
    percentage: float


class BookingSourceSplit(BaseModel):
    client_bookings_percent: float
    facility_bookings_percent: float


class TransportDistributionResponse(BaseModel):
    period_days: int
    total: int
    distribution: list[TransportTypeSlice]
    booking_source: BookingSourceSplit


# ---- Top Fleet Partners ----

class FleetPartnerEntry(BaseModel):
    rank: int
    fleet_id: UUID
    fleet_name: str
    logo_url: str | None = None
    vehicle_count: int
    total_trips: int
    average_rating: float


class TopFleetPartnersResponse(BaseModel):
    period_days: int
    partners: list[FleetPartnerEntry]
