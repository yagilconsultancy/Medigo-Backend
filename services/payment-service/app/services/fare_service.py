import logging

from app.models.fare_breakdown import FareBreakdown
from app.repositories.fare_repo import FareBreakdownRepository
from mediride_common.schemas.enums import RideType

logger = logging.getLogger(__name__)

# Configurable rate constants
BASE_RATES = {
    RideType.STANDARD: 5.00,
    RideType.WHEELCHAIR: 8.00,
    RideType.STRETCHER: 15.00,
}
PER_MILE_RATE = 1.50
MEDICAL_ASSIST_PREMIUM = 3.00
PLATFORM_FEE_PERCENT = 0.20  # 20%
SERVICE_FEE = 2.50


class FareService:
    def __init__(self, fare_repo: FareBreakdownRepository):
        self.fare_repo = fare_repo

    async def calculate_fare(self, ride_data: dict) -> FareBreakdown:
        ride_type = ride_data.get("ride_type", RideType.STANDARD)
        distance = float(ride_data.get("distance_miles", 0))

        base_fare = BASE_RATES.get(ride_type, BASE_RATES[RideType.STANDARD])
        distance_charge = round(distance * PER_MILE_RATE, 2)

        medical_premium = 0.0
        if ride_type in (RideType.WHEELCHAIR, RideType.STRETCHER):
            medical_premium = MEDICAL_ASSIST_PREMIUM

        subtotal = base_fare + distance_charge + medical_premium
        platform_fee = round(subtotal * PLATFORM_FEE_PERCENT, 2)
        total_fare = round(subtotal + SERVICE_FEE, 2)
        driver_earnings = round(total_fare - platform_fee, 2)

        breakdown = FareBreakdown(
            ride_id=ride_data["ride_id"],
            base_fare=base_fare,
            distance_charge=distance_charge,
            medical_assist_premium=medical_premium,
            service_fee=SERVICE_FEE,
            platform_fee=platform_fee,
            tips=0,
            incentives_bonuses=0,
            total_fare=total_fare,
            driver_earnings=driver_earnings,
        )
        return await self.fare_repo.create(breakdown)

    async def get_fare_breakdown(self, ride_id) -> FareBreakdown | None:
        return await self.fare_repo.get_by_ride_id(ride_id)
