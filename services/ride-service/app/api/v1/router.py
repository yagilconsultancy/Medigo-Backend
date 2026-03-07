from fastapi import APIRouter

from app.api.v1.driver_ride_endpoints import router as driver_router
from app.api.v1.rating_endpoints import router as rating_router
from app.api.v1.recurring_ride_endpoints import router as recurring_router
from app.api.v1.ride_endpoints import router as ride_router
from app.api.v1.rider_endpoints import router as rider_router
from app.api.v1.safety_endpoints import router as safety_router

router = APIRouter()

router.include_router(ride_router, tags=["Rides"])
router.include_router(rider_router, tags=["Rider"])
router.include_router(driver_router, prefix="/driver", tags=["Driver Rides"])
router.include_router(rating_router, tags=["Ratings"])
router.include_router(recurring_router, prefix="/recurring", tags=["Recurring Rides"])
router.include_router(safety_router, tags=["Safety"])
