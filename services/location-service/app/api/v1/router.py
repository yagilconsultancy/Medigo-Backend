from fastapi import APIRouter

from app.api.v1.location_endpoints import router as location_router

router = APIRouter()
router.include_router(location_router, tags=["Locations"])
