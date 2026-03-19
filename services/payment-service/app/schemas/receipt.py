from pydantic import BaseModel


class ReceiptResponse(BaseModel):
    trip_number: str
    status: str
    ride_date: str | None = None
    duration_minutes: int
    distance_miles: float
    distance_km: float | None = None
    pickup_address: str
    destination_address: str
    base_fare: float
    distance_charge: float
    medical_assist_premium: float
    service_fee: float
    wait_time_minutes: int | None = None
    wait_time_charge: float | None = None
    surcharges_total: float | None = None
    surcharges_capped: float | None = None
    surcharge_details: list[dict] | None = None
    highway_407_toll: float | None = None
    insurance_gateway_fee: float | None = None
    flat_surcharge: float | None = None
    platform_fee: float | None = None
    total_fare: float
    driver_earnings: float | None = None
    is_dialysis_rate: bool | None = None
    rate_card_version: int | None = None
    currency: str = "CAD"
    payment_method_type: str
    payment_method_last_four: str
    paid_at: str | None = None
