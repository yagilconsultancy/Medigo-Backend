from fastapi import APIRouter

from app.api.v1.user_endpoints import router as user_router
from app.api.v1.business_endpoints import router as business_router
from app.api.v1.driver_endpoints import router as driver_router
from app.api.v1.document_endpoints import router as document_router
from app.api.v1.passenger_endpoints import router as passenger_router
from app.api.v1.vehicle_endpoints import router as vehicle_router
from app.api.v1.settings_endpoints import router as settings_router
from app.api.v1.saved_location_endpoints import router as saved_location_router

router = APIRouter()
router.include_router(user_router, tags=["Users"])
router.include_router(business_router, tags=["Businesses"])
router.include_router(driver_router, tags=["Drivers"])
router.include_router(document_router, tags=["Documents"])
router.include_router(passenger_router, tags=["Passengers"])
router.include_router(vehicle_router, tags=["Vehicle & Avatar"])
router.include_router(settings_router, tags=["Settings"])
router.include_router(saved_location_router, tags=["Saved Locations"])
