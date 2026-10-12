from fastapi import APIRouter, Query, Depends
from mediride_common.auth.internal import require_internal_service as _verify_internal
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_gmaps_client
from app.repositories.geocoding_cache_repo import GeocodingCacheRepository
from app.services.distance_service import DistanceService
from app.services.geocoding_service import GeocodingService

router = APIRouter(prefix="/internal/locations", tags=["Internal"])


@router.get("/distance")
async def internal_calculate_distance(
    origin_lat: float = Query(...),
    origin_lng: float = Query(...),
    dest_lat: float = Query(...),
    dest_lng: float = Query(...),
    _caller: str = Depends(_verify_internal),
):
    """Internal endpoint for inter-service distance calculation."""
    gmaps = get_gmaps_client()
    service = DistanceService(gmaps)
    result = await service.calculate_distance(origin_lat, origin_lng, dest_lat, dest_lng)
    return result or {"error": "Could not calculate distance"}


@router.get("/geocode")
async def internal_geocode(
    address: str = Query(...),
    session: AsyncSession = Depends(get_db),
    _caller: str = Depends(_verify_internal),
):
    """Internal endpoint for inter-service geocoding."""
    gmaps = get_gmaps_client()
    service = GeocodingService(GeocodingCacheRepository(session), gmaps)
    result = await service.geocode(address)
    return result or {"error": "Could not geocode address"}
