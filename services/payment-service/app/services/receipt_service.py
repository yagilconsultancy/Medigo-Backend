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
            "pickup_address": ride_data.get("pickup_address", ""),
            "destination_address": ride_data.get("destination_address", ""),
            "base_fare": float(breakdown.base_fare) if breakdown else 0,
            "distance_charge": float(breakdown.distance_charge) if breakdown else 0,
            "medical_assist_premium": float(breakdown.medical_assist_premium) if breakdown else 0,
            "service_fee": float(breakdown.service_fee) if breakdown else 0,
            "total_fare": float(breakdown.total_fare) if breakdown else float(ride_data.get("final_fare") or 0),
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
