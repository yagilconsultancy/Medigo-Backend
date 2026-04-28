from pydantic import BaseModel, Field


class BookingAudienceOption(BaseModel):
    code: str
    role: str
    label: str
    description: str
    features: list[str] = Field(default_factory=list)


class BookingServiceOption(BaseModel):
    trip_type: str
    label: str
    description: str
    features: list[str] = Field(default_factory=list)
    recommended: bool = False
    requires_scheduled: bool = False


class BookingAppointmentOption(BaseModel):
    visit_type: str
    label: str
    description: str
    is_dialysis_trip: bool = False


class BookingVehicleOption(BaseModel):
    ride_type: str
    label: str
    description: str
    features: list[str] = Field(default_factory=list)


class BookingTripStructureOption(BaseModel):
    trip_structure: str
    label: str
    description: str


class BookingRecurringFrequencyOption(BaseModel):
    frequency: str
    label: str
    description: str


class PublicBookingConfigResponse(BaseModel):
    audiences: list[BookingAudienceOption]
    services: list[BookingServiceOption]
    appointments: list[BookingAppointmentOption]
    vehicles: list[BookingVehicleOption]
    trip_structures: list[BookingTripStructureOption]
    recurring_frequencies: list[BookingRecurringFrequencyOption]
