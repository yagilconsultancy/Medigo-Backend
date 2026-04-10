from fastapi import APIRouter

from app.api.v1.user_endpoints import router as user_router
from app.api.v1.driver_endpoints import router as driver_router
from app.api.v1.document_endpoints import router as document_router
from app.api.v1.passenger_endpoints import router as passenger_router
from app.api.v1.vehicle_endpoints import router as vehicle_router
from app.api.v1.settings_endpoints import router as settings_router
from app.api.v1.saved_location_endpoints import router as saved_location_router
from app.api.v1.fleet_application_endpoints import router as fleet_app_router
from app.api.v1.fleet_company_endpoints import router as fleet_company_router
from app.api.v1.fleet_vehicle_endpoints import router as fleet_vehicle_router
from app.api.v1.fleet_earnings_endpoints import router as fleet_earnings_router
from app.api.v1.admin_driver_endpoints import router as admin_driver_router
from app.api.v1.admin_rider_endpoints import router as admin_rider_router
from app.api.v1.caregiver_endpoints import router as caregiver_router

router = APIRouter()
router.include_router(user_router, tags=["Users"])
router.include_router(driver_router, tags=["Drivers"])
router.include_router(document_router, tags=["Documents"])
router.include_router(passenger_router, tags=["Passengers"])
router.include_router(vehicle_router, tags=["Vehicle & Avatar"])
router.include_router(settings_router, tags=["Settings"])
router.include_router(saved_location_router, tags=["Saved Locations"])
router.include_router(fleet_app_router, tags=["Fleet Applications"])
router.include_router(fleet_company_router, tags=["Fleet Companies"])
router.include_router(fleet_vehicle_router, tags=["Fleet Vehicles"])
router.include_router(fleet_earnings_router, tags=["Fleet Earnings"])
router.include_router(admin_driver_router, tags=["Admin Driver Management"])
router.include_router(admin_rider_router, tags=["Admin Rider Management"])
router.include_router(caregiver_router, tags=["Service Provider (Caregivers)"])
