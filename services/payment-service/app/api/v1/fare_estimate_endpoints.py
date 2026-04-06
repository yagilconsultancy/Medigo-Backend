import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.location_service_client import LocationServiceClient
from app.config import settings
from app.dependencies import get_db
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository
from app.repositories.weather_condition_repo import WeatherConditionRepository
from app.schemas.rate_card import RiderFareEstimateRequest, RiderFareEstimateResponse
from app.services.fare_service import FareService
from mediride_common.schemas.responses import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _location_client() -> LocationServiceClient:
    return LocationServiceClient(settings.LOCATION_SERVICE_URL)


@router.post("/fare-estimate", response_model=StandardResponse[RiderFareEstimateResponse])
async def rider_fare_estimate(
    body: RiderFareEstimateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Calculate a fare estimate using real Google Maps distance.

    **PUBLIC ENDPOINT** - No authentication required.
    Riders can get fare estimates before booking or logging in.

    Accepts pickup and destination as addresses and/or coordinates.
    Automatically geocodes addresses and calculates driving distance.
    """
    location_client = _location_client()

    # --- Resolve pickup coordinates ---
    pickup_lat = body.pickup_latitude
    pickup_lng = body.pickup_longitude
    pickup_address = body.pickup_address

    if pickup_lat is None or pickup_lng is None:
        geo = await location_client.geocode(body.pickup_address)
        if not geo:
            raise HTTPException(
                status_code=422,
                detail="Could not geocode pickup address. Provide valid coordinates or a more specific address.",
            )
        pickup_lat = geo["latitude"]
        pickup_lng = geo["longitude"]
        if not pickup_address:
            pickup_address = geo.get("formatted_address", "")

    # --- Resolve destination coordinates ---
    dest_lat = body.destination_latitude
    dest_lng = body.destination_longitude
    dest_address = body.destination_address

    if dest_lat is None or dest_lng is None:
        geo = await location_client.geocode(body.destination_address)
        if not geo:
            raise HTTPException(
                status_code=422,
                detail="Could not geocode destination address. Provide valid coordinates or a more specific address.",
            )
        dest_lat = geo["latitude"]
        dest_lng = geo["longitude"]
        if not dest_address:
            dest_address = geo.get("formatted_address", "")

    # --- Calculate driving distance ---
    distance_result = await location_client.calculate_distance(
        origin_lat=pickup_lat,
        origin_lng=pickup_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
    )
    if not distance_result:
        raise HTTPException(
            status_code=503,
            detail="Could not calculate distance. Please try again later.",
        )

    distance_miles = distance_result["distance_miles"]
    distance_km = distance_result["distance_km"]
    duration_minutes = distance_result["duration_minutes"]

    # --- Run fare engine ---
    scheduled_at = body.scheduled_at or datetime.now(timezone.utc)

    fare_service = FareService(
        fare_repo=FareBreakdownRepository(session),
        rate_card_repo=RateCardRepository(session),
        holiday_repo=HolidayRepository(session),
        weather_repo=WeatherConditionRepository(session),
        dialysis_repo=DialysisRatePlanRepository(session),
        service_type_repo=ServiceTypeConfigRepository(session),
    )

    estimate = await fare_service.estimate_fare(
        {
            "distance_miles": distance_miles,
            "scheduled_at": scheduled_at.isoformat(),
            "pickup_address": pickup_address or "",
            "destination_address": dest_address or "",
            "use_highway_407": body.use_highway_407,
            "highway_407_route": body.highway_407_route,
            "is_dialysis_trip": body.is_dialysis_trip,
            "ride_type": body.ride_type,
            "trip_type": body.trip_type,
            "trip_structure": body.trip_structure,
            "timeline": [],
        }
    )

    return StandardResponse(
        data=RiderFareEstimateResponse(
            distance_km=distance_km,
            distance_miles=distance_miles,
            duration_minutes=duration_minutes,
            base_fare=estimate["base_fare"],
            distance_charge=estimate["distance_charge"],
            wait_time_charge=estimate["wait_time_charge"],
            surcharges_total=estimate["surcharges_total"],
            surcharges_capped=estimate["surcharges_capped"],
            surcharge_details=estimate["surcharge_details"],
            highway_407_toll=estimate["highway_407_toll"],
            insurance_gateway_fee=estimate["insurance_gateway_fee"],
            flat_surcharge=estimate["flat_surcharge"],
            platform_fee=estimate["platform_fee"],
            total_fare=estimate["total_fare"],
            driver_earnings=estimate["driver_earnings"],
            is_dialysis_rate=estimate["is_dialysis_rate"],
            rate_card_version=estimate["rate_card_version"],
            care_assistant_fee=estimate["care_assistant_fee"],
            accessibility_fee=estimate["accessibility_fee"],
            attendant_fee=estimate["attendant_fee"],
            is_round_trip=estimate["is_round_trip"],
            return_distance_charge=estimate["return_distance_charge"],
            ride_type=estimate["ride_type"],
            trip_type=estimate["trip_type"],
            currency=settings.DEFAULT_CURRENCY,
            estimated_at=datetime.now(timezone.utc),
        )
    )
