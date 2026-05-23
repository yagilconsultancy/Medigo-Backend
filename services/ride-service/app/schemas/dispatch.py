"""Schemas for Dispatch Center functionality."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# --- Dispatch Center Dashboard KPIs ---

class DispatchKPIs(BaseModel):
    pending_assignments: int
    assigned_today: int
    available_drivers: int
    drivers_on_trip: int


# --- Unassigned Ride Item ---

class UnassignedRideItem(BaseModel):
    ride_id: UUID
    booking_number: str
    rider_name: str
    ride_type: str
    pickup_address: str
    destination_address: str
    scheduled_at: datetime
    distance_km: float | None = None
    estimated_fare: float | None = None
    patient_name: str | None = None
    rider_role: str | None = None
    special_requirements: list[str] = []
    assigned_status: str | None = None  # For "Assigned" tag in UI


# --- Available Driver Item ---

class AvailableDriverItem(BaseModel):
    driver_id: UUID
    driver_name: str
    vehicle_type: str
    vehicle_info: str  # e.g., "Toyota Camry - 2021"
    rating: float
    total_trips: int
    distance_from_pickup: float | None = None  # km
    eta_minutes: int | None = None
    specialty: str | None = None
    fleet_name: str | None = None


# --- Dispatch Center Dashboard Response ---

class DispatchDashboardResponse(BaseModel):
    kpis: DispatchKPIs
    unassigned_rides: list[UnassignedRideItem]
    available_drivers: list[AvailableDriverItem]


# --- Auto Dispatch Settings ---

class DispatchPriorityRules(BaseModel):
    prioritize_by_rating: bool = True
    prioritize_by_fleet: bool = False
    match_vehicle_type: bool = True


class DistanceMatchingLogic(BaseModel):
    search_radius_km: int = Field(5, ge=2, le=15)  # 2, 5, 10, or 15 km


class FallbackBehavior(BaseModel):
    expand_search_radius: bool = True
    notify_dispatch_team: bool = False
    notify_rider: bool = False


class AutoDispatchSettings(BaseModel):
    id: UUID | None = None
    auto_dispatch_enabled: bool = False
    distance_matching: DistanceMatchingLogic = DistanceMatchingLogic()
    priority_rules: DispatchPriorityRules = DispatchPriorityRules()
    fallback_behavior: FallbackBehavior = FallbackBehavior()
    updated_at: datetime | None = None
    updated_by: UUID | None = None


class UpdateAutoDispatchSettingsRequest(BaseModel):
    auto_dispatch_enabled: bool
    distance_matching: DistanceMatchingLogic
    priority_rules: DispatchPriorityRules
    fallback_behavior: FallbackBehavior


# --- Manual Assignment Request ---

class ManualAssignmentRequest(BaseModel):
    driver_id: UUID


# --- Auto Assignment Response ---

class AutoAssignmentResult(BaseModel):
    ride_id: UUID
    driver_id: UUID | None
    assigned: bool
    reason: str | None = None  # e.g., "No drivers available within radius"


class TriggerAutoDispatchResponse(BaseModel):
    total_rides: int
    assigned_count: int
    failed_count: int
    results: list[AutoAssignmentResult]
