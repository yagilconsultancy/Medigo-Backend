from fastapi import APIRouter

from app.api.v1.city_endpoints import router as city_router
from app.api.v1.location_endpoints import router as location_router

router = APIRouter()
router.include_router(location_router, tags=["Locations"])
router.include_router(city_router, tags=["Cities & Service Areas"])
