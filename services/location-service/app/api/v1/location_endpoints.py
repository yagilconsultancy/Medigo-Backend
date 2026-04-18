from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_gmaps_client
from app.repositories.geocoding_cache_repo import GeocodingCacheRepository
from app.repositories.service_area_repo import ServiceAreaRepository
from app.schemas.location import (
    AutocompleteResult,
    DistanceResponse,
    GeocodeResponse,
    PlaceDetailsResponse,
    ReverseGeocodeResponse,
    ServiceAreaCheckResponse,
)
from app.services.distance_service import DistanceService
from app.services.geocoding_service import GeocodingService
from app.services.service_area_service import ServiceAreaService
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


@router.get("/public/check-address", response_model=StandardResponse[GeocodeResponse])
async def check_address_public(
    address: str = Query(..., min_length=3, max_length=500),
    session: AsyncSession = Depends(get_db),
):
    """
    Public endpoint to validate and geocode an address without authentication.
    Useful for address validation during signup or booking flows.
    """
    gmaps = get_gmaps_client()
    service = GeocodingService(GeocodingCacheRepository(session), gmaps)
    result = await service.geocode(address)
    if not result:
        raise NotFoundError("Could not validate address. Please check the address and try again.")
    return StandardResponse(
        data=GeocodeResponse(**result),
        message="Address validated successfully",
    )


@router.get("/geocode", response_model=StandardResponse[GeocodeResponse])
async def geocode_address(
    address: str = Query(..., min_length=3, max_length=500),
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Geocode an address to lat/lng coordinates."""
    gmaps = get_gmaps_client()
    service = GeocodingService(GeocodingCacheRepository(session), gmaps)
    result = await service.geocode(address)
    if not result:
        raise NotFoundError("Could not geocode address")
    return StandardResponse(data=GeocodeResponse(**result), message="Address geocoded")


@router.get("/reverse-geocode", response_model=StandardResponse[ReverseGeocodeResponse])
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Reverse geocode lat/lng to an address."""
    gmaps = get_gmaps_client()
    service = GeocodingService(GeocodingCacheRepository(session), gmaps)
    result = await service.reverse_geocode(lat, lng)
    if not result:
        raise NotFoundError("Could not reverse geocode location")
    return StandardResponse(data=ReverseGeocodeResponse(**result), message="Location reverse geocoded")


@router.get("/autocomplete", response_model=StandardResponse[list[AutocompleteResult]])
async def autocomplete_address(
    query: str = Query(..., min_length=2, max_length=200),
    lat: float | None = Query(None, ge=-90, le=90),
    lng: float | None = Query(None, ge=-180, le=180),
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get address autocomplete suggestions."""
    gmaps = get_gmaps_client()
    service = GeocodingService(GeocodingCacheRepository(session), gmaps)
    results = await service.autocomplete(query, lat, lng)
    return StandardResponse(
        data=[AutocompleteResult(**r) for r in results],
        message=f"{len(results)} suggestions found",
    )


@router.get("/distance", response_model=StandardResponse[DistanceResponse])
async def calculate_distance(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lng: float = Query(..., ge=-180, le=180),
    dest_lat: float = Query(..., ge=-90, le=90),
    dest_lng: float = Query(..., ge=-180, le=180),
    user: UserClaims = Depends(get_current_user),
):
    """Calculate distance and duration between two points."""
    gmaps = get_gmaps_client()
    service = DistanceService(gmaps)
    result = await service.calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng)
    if not result:
        raise NotFoundError("Could not calculate distance")
    return StandardResponse(data=DistanceResponse(**result), message="Distance calculated")


@router.get("/service-area/check", response_model=StandardResponse[ServiceAreaCheckResponse])
async def check_service_area(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Check if a location is within a service area."""
    service = ServiceAreaService(ServiceAreaRepository(session))
    area = await service.get_service_area(lat, lng)
    if area:
        return StandardResponse(
            data=ServiceAreaCheckResponse(in_service_area=True, area_name=area["name"], area_id=area["id"]),
            message="Location is in service area",
        )
    return StandardResponse(
        data=ServiceAreaCheckResponse(in_service_area=False),
        message="Location is not in any service area",
    )


@router.get("/place/{place_id}", response_model=StandardResponse[PlaceDetailsResponse])
async def get_place_details(
    place_id: str,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get detailed information about a place."""
    gmaps = get_gmaps_client()
    service = GeocodingService(GeocodingCacheRepository(session), gmaps)
    result = await service.place_details(place_id)
    if not result:
        raise NotFoundError("Place not found")
    return StandardResponse(data=PlaceDetailsResponse(**result), message="Place details retrieved")
