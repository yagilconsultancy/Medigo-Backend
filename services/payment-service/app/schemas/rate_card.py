from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ---- Rate Card Config Sub-Schemas ----

class BaseFareConfig(BaseModel):
    flat_rate: float = 12.00
    distance_threshold_km: float = 10.0
    per_km_beyond_threshold: float = 0.75


class FeesConfig(BaseModel):
    surcharge_flat_per_trip: float = 0.06
    insurance_payment_gateway_fee: float = 1.50


class WaitTimeConfig(BaseModel):
    free_minutes: int = 10
    per_minute_after_free: float = 0.50


class TimeSurchargeRule(BaseModel):
    name: str
    days: list[int] | None = None  # 0=Mon..6=Sun; None means any day
    start: str  # "HH:MM"
    end: str  # "HH:MM"
    amount: float


class WeekendSurchargeConfig(BaseModel):
    saturday: float = 3.00
    sunday: float = 4.00


class Highway407TollConfig(BaseModel):
    milton_oakville: float = 8.00
    milton_brampton: float = 9.00
    milton_mississauga: float = 10.00


class WeatherSurchargeConfig(BaseModel):
    light_snow: float = 3.00
    heavy_snow: float = 5.00
    post_storm: float = 3.00


class RateCardConfig(BaseModel):
    timezone: str = "America/Toronto"
    base_fare: BaseFareConfig = BaseFareConfig()
    fees: FeesConfig = FeesConfig()
    wait_time: WaitTimeConfig = WaitTimeConfig()
    max_surcharge_cap: float = 18.00
    platform_fee_percent: float = 0.20
    weather_surcharges: WeatherSurchargeConfig = WeatherSurchargeConfig()
    rush_hour_surcharges: list[TimeSurchargeRule] = []
    time_of_day_surcharges: list[TimeSurchargeRule] = []
    weekend_surcharges: WeekendSurchargeConfig = WeekendSurchargeConfig()
    holiday_surcharge: float = 5.00
    highway_407_tolls: Highway407TollConfig = Highway407TollConfig()


# ---- Request Schemas ----

class CreateRateCardRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    config: RateCardConfig
    notes: str | None = None


class HolidayCreateRequest(BaseModel):
    date: date
    name: str = Field(..., min_length=1, max_length=200)


class WeatherToggleRequest(BaseModel):
    condition_type: str = Field(..., min_length=1, max_length=30)
    is_active: bool
    notes: str | None = None


class DialysisRatePlanCreateRequest(BaseModel):
    plan_name: str = Field(..., min_length=1, max_length=200)
    origin_area: str = Field(..., min_length=1, max_length=200)
    destination_area: str = Field(..., min_length=1, max_length=200)
    per_trip_rate: float = Field(..., gt=0)
    monthly_package_rate: float | None = None
    monthly_package_trips: int | None = None
    min_trips_per_week: int | None = None


class DialysisRatePlanUpdateRequest(BaseModel):
    plan_name: str | None = None
    origin_area: str | None = None
    destination_area: str | None = None
    per_trip_rate: float | None = Field(default=None, gt=0)
    monthly_package_rate: float | None = None
    monthly_package_trips: int | None = None
    min_trips_per_week: int | None = None
    is_active: bool | None = None


class FareEstimateRequest(BaseModel):
    pickup_address: str
    destination_address: str
    distance_miles: float = Field(..., ge=0)
    scheduled_at: datetime
    use_highway_407: bool = False
    highway_407_route: str | None = None
    is_dialysis_trip: bool = False


class RiderFareEstimateRequest(BaseModel):
    """Fare estimate request for riders — auto-calculates distance via Google Maps."""

    pickup_address: str | None = None
    pickup_latitude: float | None = None
    pickup_longitude: float | None = None

    destination_address: str | None = None
    destination_latitude: float | None = None
    destination_longitude: float | None = None

    scheduled_at: datetime | None = None  # defaults to now
    use_highway_407: bool = False
    highway_407_route: str | None = None
    is_dialysis_trip: bool = False

    @model_validator(mode="after")
    def validate_locations(self):
        has_pickup = bool(self.pickup_address) or (
            self.pickup_latitude is not None and self.pickup_longitude is not None
        )
        has_dest = bool(self.destination_address) or (
            self.destination_latitude is not None and self.destination_longitude is not None
        )
        if not has_pickup:
            raise ValueError("Provide pickup_address or pickup_latitude + pickup_longitude")
        if not has_dest:
            raise ValueError("Provide destination_address or destination_latitude + destination_longitude")
        return self


# ---- Response Schemas ----

class RateCardResponse(BaseModel):
    id: UUID
    version: int
    name: str
    config: dict
    is_active: bool
    created_by: UUID
    notes: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RateCardSummaryResponse(BaseModel):
    id: UUID
    version: int
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class HolidayResponse(BaseModel):
    id: UUID
    date: date
    name: str
    is_active: bool
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class WeatherConditionResponse(BaseModel):
    id: UUID
    condition_type: str
    is_active: bool
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    activated_by: UUID | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DialysisRatePlanResponse(BaseModel):
    id: UUID
    plan_name: str
    origin_area: str
    destination_area: str
    per_trip_rate: float
    monthly_package_rate: float | None = None
    monthly_package_trips: int | None = None
    min_trips_per_week: int | None = None
    is_active: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FareEstimateResponse(BaseModel):
    base_fare: float
    distance_km: float
    distance_charge: float
    wait_time_minutes: int
    wait_time_charge: float
    surcharges_total: float
    surcharges_capped: float
    surcharge_details: list[dict]
    highway_407_toll: float
    insurance_gateway_fee: float
    flat_surcharge: float
    platform_fee: float
    total_fare: float
    driver_earnings: float
    is_dialysis_rate: bool
    rate_card_version: int


class RiderFareEstimateResponse(BaseModel):
    """Fare estimate response for riders — includes distance and duration."""

    distance_km: float
    distance_miles: float
    duration_minutes: float

    base_fare: float
    distance_charge: float
    surcharges_total: float
    surcharges_capped: float
    surcharge_details: list[dict]
    highway_407_toll: float
    insurance_gateway_fee: float
    flat_surcharge: float
    total_fare: float
    is_dialysis_rate: bool
    rate_card_version: int

    currency: str = "CAD"
    estimated_at: datetime
