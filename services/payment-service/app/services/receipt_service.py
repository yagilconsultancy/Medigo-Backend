import logging
from uuid import UUID

from app.clients.ride_service_client import RideServiceClient
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from mediride_common.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class ReceiptService:
    def __init__(
        self,
        fare_repo: FareBreakdownRepository,
        pm_repo: PaymentMethodRepository,
        ride_client: RideServiceClient,
    ):
        self.fare_repo = fare_repo
        self.pm_repo = pm_repo
        self.ride_client = ride_client

    async def generate_receipt(self, ride_id: UUID, user_id: UUID) -> dict:
        ride_data = await self.ride_client.get_ride(ride_id)
        if not ride_data:
            raise NotFoundError("Ride not found")

        breakdown = await self.fare_repo.get_by_ride_id(ride_id)

        trip_number = f"TRIP-{str(ride_id)[:6].upper()}"

        receipt = {
            "trip_number": trip_number,
            "status": ride_data.get("status", "completed"),
            "ride_date": ride_data.get("scheduled_at"),
            "duration_minutes": ride_data.get("actual_duration_minutes") or ride_data.get("estimated_duration_minutes") or 0,
            "distance_miles": float(ride_data.get("actual_distance_miles") or ride_data.get("estimated_distance_miles") or 0),
            "distance_km": float(breakdown.distance_km) if breakdown and breakdown.distance_km else None,
            "pickup_address": ride_data.get("pickup_address", ""),
            "destination_address": ride_data.get("destination_address", ""),
            "base_fare": float(breakdown.base_fare) if breakdown else 0,
            "distance_charge": float(breakdown.distance_charge) if breakdown else 0,
            "medical_assist_premium": float(breakdown.medical_assist_premium) if breakdown else 0,
            "service_fee": float(breakdown.service_fee) if breakdown else 0,
            "wait_time_minutes": breakdown.wait_time_minutes if breakdown else None,
            "wait_time_charge": float(breakdown.wait_time_charge) if breakdown and breakdown.wait_time_charge else None,
            "surcharges_total": float(breakdown.surcharges_total) if breakdown and breakdown.surcharges_total else None,
            "surcharges_capped": float(breakdown.surcharges_capped) if breakdown and breakdown.surcharges_capped else None,
            "surcharge_details": breakdown.surcharge_details if breakdown else None,
            "highway_407_toll": float(breakdown.highway_407_toll) if breakdown and breakdown.highway_407_toll else None,
            "insurance_gateway_fee": float(breakdown.insurance_gateway_fee) if breakdown and breakdown.insurance_gateway_fee else None,
            "flat_surcharge": float(breakdown.flat_surcharge) if breakdown and breakdown.flat_surcharge else None,
            "platform_fee": float(breakdown.platform_fee) if breakdown else None,
            "total_fare": float(breakdown.total_fare) if breakdown else float(ride_data.get("final_fare") or 0),
            "driver_earnings": float(breakdown.driver_earnings) if breakdown else None,
            "is_dialysis_rate": breakdown.is_dialysis_rate if breakdown else None,
            "rate_card_version": breakdown.rate_card_version if breakdown else None,
            "currency": "CAD",
            "payment_method_type": "",
            "payment_method_last_four": "",
            "paid_at": None,
        }

        # Get payment method info
        methods = await self.pm_repo.get_by_user(user_id)
        if methods:
            default = next((m for m in methods if m.is_default), methods[0])
            receipt["payment_method_type"] = default.method_type
            receipt["payment_method_last_four"] = default.last_four

        return receipt
