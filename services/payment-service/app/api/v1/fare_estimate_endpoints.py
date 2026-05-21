import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.location_service_client import LocationServiceClient
from app.config import settings
from app.dependencies import get_db
from app.repositories.cancellation_policy_repo import CancellationPolicyRepository
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository
from app.repositories.weather_condition_repo import WeatherConditionRepository
from app.schemas.rate_card import (
    BaseFareEstimateRequest,
    BaseFareEstimateResponse,
    BaseFareEstimateItem,
    CancellationFeeInfo,
    RiderFareEstimateArrayResponse,
    RiderFareEstimateItem,
    RiderFareEstimateRequest,
    RiderFareEstimateResponse,
)
from app.services.fare_service import FareService
from mediride_common.schemas.responses import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_BASE_SERVICE_TYPE_PROFILE = {
    "standard": {"ride_type": "ambulatory", "trip_type": "transport_only"},
    "wheelchair_wav": {"ride_type": "wheelchair", "trip_type": "transport_only"},
    "stretcher": {"ride_type": "stretcher", "trip_type": "transport_only"},
    "psw_caregiver": {
        "ride_type": "ambulatory",
        "trip_type": "transport_care_assistant",
    },
}


def _location_client() -> LocationServiceClient:
    return LocationServiceClient(settings.LOCATION_SERVICE_URL)


def _base_estimate_profile_for_service_type(service_type: str) -> dict | None:
    return _BASE_SERVICE_TYPE_PROFILE.get(service_type)


def _base_estimate_copy_for_service_type(service_type: str) -> dict:
    passengers = "Up to 3 passengers"
    description = "Comfortable assisted transport for mobile patients."
    best_for = "Routine appointments and light mobility support"
    features = ["Door-to-door assistance", "Boarding support"]

    if service_type == "wheelchair_wav":
        passengers = "1 wheelchair + 2"
        description = "Safe and secure transport for wheelchair users"
        best_for = "Patients requiring ramp or lift access"
        features = ["ADA-compliant lift or ramp", "Secure wheelchair locking"]
    elif service_type == "stretcher":
        passengers = "1 stretcher"
        description = "Full medical transport for patients unable to sit upright"
        best_for = "Post-surgery, injury recovery, and non-emergency medical needs"
        features = [
            "Stretcher-compatible vehicle",
            "Emergency-trained staff",
            "Two-person medical support",
        ]
    elif service_type == "psw_caregiver":
        passengers = "Up to 3 passengers"
        description = "Transport with professional caregiver assistance"
        best_for = "Patients needing personal support worker care"
        features = [
            "Certified PSW caregiver",
            "Medication assistance",
            "Personal care support",
        ]

    return {
        "passengers": passengers,
        "description": description,
        "best_for": best_for,
        "features": features,
    }


async def _get_cancellation_fees(
    session: AsyncSession, service_type: str
) -> list[CancellationFeeInfo]:
    """Fetch active cancellation fee tiers for a service type."""
    repo = CancellationPolicyRepository(session)
    policies = await repo.get_by_service_type(service_type)
    return [
        CancellationFeeInfo(
            cancellation_window=p.cancellation_window,
            fee=p.fee,
        )
        for p in policies
    ]


@router.post("/fare-estimate")
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

    **ride_type**: Set to "all" to get estimates for all ride types, or specify a specific type.
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

    # --- Check if requesting all ride types ---
    if body.ride_type == "all":
        service_type_repo = ServiceTypeConfigRepository(session)
        service_types = await service_type_repo.get_all(active_only=True)

        estimates_list = []
        for service_type in service_types:
            estimate = await fare_service.estimate_fare(
                {
                    "distance_miles": distance_miles,
                    "scheduled_at": scheduled_at.isoformat(),
                    "pickup_address": pickup_address or "",
                    "destination_address": dest_address or "",
                    "use_highway_407": body.use_highway_407,
                    "highway_407_route": body.highway_407_route,
                    "is_dialysis_trip": body.is_dialysis_trip,
                    "ride_type": service_type.service_type,
                    "trip_type": body.trip_type,
                    "trip_structure": body.trip_structure,
                    "timeline": [],
                }
            )

            cancellation_fees = await _get_cancellation_fees(
                session, service_type.service_type
            )

            estimates_list.append(
                RiderFareEstimateItem(
                    service_type=service_type.service_type,
                    display_name=service_type.display_name,
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
                    cancellation_fees=cancellation_fees,
                )
            )

        return StandardResponse(
            data=RiderFareEstimateArrayResponse(
                distance_km=distance_km,
                distance_miles=distance_miles,
                duration_minutes=duration_minutes,
                estimates=estimates_list,
                currency=settings.DEFAULT_CURRENCY,
                estimated_at=datetime.now(timezone.utc),
            )
        )

    # --- Single ride type estimate ---
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

    cancellation_fees = await _get_cancellation_fees(session, body.ride_type)

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
            cancellation_fees=cancellation_fees,
            currency=settings.DEFAULT_CURRENCY,
            estimated_at=datetime.now(timezone.utc),
        )
    )


@router.post("/base-fare-estimate", response_model=StandardResponse[BaseFareEstimateResponse])
async def calculate_base_fare(
    body: BaseFareEstimateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Calculate comparison fare estimates for supported ride types using the main fare engine.

    **PUBLIC ENDPOINT** - No authentication required.

    Automatically calculates distance from pickup to destination using Google Maps.
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

    distance_km = distance_result["distance_km"]
    distance_miles = distance_result["distance_miles"]
    scheduled_at = body.scheduled_at or datetime.now(timezone.utc)

    fare_service = FareService(
        fare_repo=FareBreakdownRepository(session),
        rate_card_repo=RateCardRepository(session),
        holiday_repo=HolidayRepository(session),
        weather_repo=WeatherConditionRepository(session),
        dialysis_repo=DialysisRatePlanRepository(session),
        service_type_repo=ServiceTypeConfigRepository(session),
    )

    # --- Get supported service types (exclude hospital_discharge until it has fare-engine support) ---
    service_type_repo = ServiceTypeConfigRepository(session)
    all_service_types = await service_type_repo.get_all(active_only=True)
    service_types = [
        st for st in all_service_types
        if _base_estimate_profile_for_service_type(st.service_type)
    ]

    estimates_list = []

    for service_type in service_types:
        profile = _base_estimate_profile_for_service_type(service_type.service_type)
        copy = _base_estimate_copy_for_service_type(service_type.service_type)
        estimate = await fare_service.estimate_fare(
            {
                "distance_miles": distance_miles,
                "scheduled_at": scheduled_at.isoformat(),
                "pickup_address": pickup_address or "",
                "destination_address": dest_address or "",
                "use_highway_407": body.use_highway_407,
                "highway_407_route": body.highway_407_route,
                "is_dialysis_trip": body.is_dialysis_trip,
                "ride_type": profile["ride_type"],
                "trip_type": profile["trip_type"],
                "trip_structure": body.trip_structure,
                "timeline": [],
            }
        )

        cancellation_fees = await _get_cancellation_fees(
            session, service_type.service_type
        )

        estimates_list.append(
            BaseFareEstimateItem(
                service_type=service_type.service_type,
                display_name=service_type.display_name,
                base_fare=estimate["base_fare"],
                distance_charge=estimate["distance_charge"],
                estimated_total=estimate["total_fare"],
                wait_time_charge=estimate["wait_time_charge"],
                surcharges_total=estimate["surcharges_total"],
                surcharges_capped=estimate["surcharges_capped"],
                highway_407_toll=estimate["highway_407_toll"],
                insurance_gateway_fee=estimate["insurance_gateway_fee"],
                flat_surcharge=estimate["flat_surcharge"],
                platform_fee=estimate["platform_fee"],
                driver_earnings=estimate["driver_earnings"],
                care_assistant_fee=estimate["care_assistant_fee"],
                accessibility_fee=estimate["accessibility_fee"],
                attendant_fee=estimate["attendant_fee"],
                rate_card_version=estimate["rate_card_version"],
                ride_type=estimate["ride_type"],
                trip_type=estimate["trip_type"],
                is_round_trip=estimate["is_round_trip"],
                return_distance_charge=estimate["return_distance_charge"],
                cancellation_fees=cancellation_fees,
                description=copy["description"],
                passengers=copy["passengers"],
                best_for=copy["best_for"],
                features=copy["features"],
            )
        )

    return StandardResponse(
        data=BaseFareEstimateResponse(
            distance_km=distance_km,
            estimates=estimates_list,
            currency=settings.DEFAULT_CURRENCY,
            estimated_at=datetime.now(timezone.utc),
        )
    )
