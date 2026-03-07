from pydantic import BaseModel


class ReceiptResponse(BaseModel):
    trip_number: str
    status: str
    ride_date: str | None = None
    duration_minutes: int
    distance_miles: float
    pickup_address: str
    destination_address: str
    base_fare: float
    distance_charge: float
    medical_assist_premium: float
    service_fee: float
    total_fare: float
    payment_method_type: str
    payment_method_last_four: str
    paid_at: str | None = None
