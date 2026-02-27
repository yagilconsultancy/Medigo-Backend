from fastapi import APIRouter

from app.api.v1.user_endpoints import router as user_router
from app.api.v1.business_endpoints import router as business_router
from app.api.v1.driver_endpoints import router as driver_router
from app.api.v1.passenger_endpoints import router as passenger_router

router = APIRouter()
router.include_router(user_router, tags=["Users"])
router.include_router(business_router, tags=["Businesses"])
router.include_router(driver_router, tags=["Drivers"])
router.include_router(passenger_router, tags=["Passengers"])
