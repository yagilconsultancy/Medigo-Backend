from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


# ---- KPI Overview ----

class KPIChange(BaseModel):
    value: float
    change_percent: float
    trend: str  # "up", "down", "flat"


class DashboardKPIs(BaseModel):
    total_bookings: KPIChange
    active_clients: KPIChange
    registered_facilities: KPIChange
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


# ---- Booking Channels ----

class BookingChannelEntry(BaseModel):
    channel: str  # "Mobile App", "Website (Client)", "Website (Facility)"
    count: int
    percentage: float
    growth_percent: float


class BookingChannelsResponse(BaseModel):
    period_days: int
    total: int
    channels: list[BookingChannelEntry]


# ---- Service Quality Metrics ----

class ServiceQualityResponse(BaseModel):
    avg_pickup_time_minutes: float
    avg_trip_distance_km: float
    service_rating: float
    completion_rate_percent: float


# ---- Top Performing Facilities ----

class TopFacilityEntry(BaseModel):
    rank: int
    facility_id: UUID
    facility_name: str
    facility_type: str | None = None
    total_bookings: int
    acceptance_rate: float


class TopFacilitiesResponse(BaseModel):
    period_days: int
    total_facilities: int
    type_counts: dict[str, int]  # {"Hospital": 5, "Care Home": 3, ...}
    facilities: list[TopFacilityEntry]
