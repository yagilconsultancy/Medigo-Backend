from fastapi import APIRouter

from app.api.v1.booking_flow_endpoints import router as booking_flow_router
from app.api.v1.guest_booking_endpoints import router as guest_booking_router
from app.api.v1.admin_alert_endpoints import router as admin_alert_router
from app.api.v1.admin_booking_endpoints import router as admin_booking_router
from app.api.v1.admin_discipline_endpoints import router as admin_discipline_router
from app.api.v1.admin_dispatch_endpoints import router as admin_dispatch_router
from app.api.v1.admin_incident_endpoints import router as admin_incident_router
from app.api.v1.admin_investigation_endpoints import router as admin_investigation_router
from app.api.v1.admin_ride_endpoints import router as admin_router
from app.api.v1.analytics_endpoints import router as analytics_router
from app.api.v1.driver_ride_endpoints import router as driver_router
from app.api.v1.rating_endpoints import router as rating_router
from app.api.v1.recurring_ride_endpoints import router as recurring_router
from app.api.v1.ride_endpoints import router as ride_router
from app.api.v1.rider_endpoints import router as rider_router
from app.api.v1.safety_endpoints import router as safety_router

router = APIRouter()

router.include_router(booking_flow_router, tags=["Public Booking Flow"])
router.include_router(guest_booking_router, tags=["Public Guest Booking"])
router.include_router(ride_router, tags=["Rides"])
router.include_router(rider_router, tags=["Rider"])
router.include_router(admin_router, prefix="/admin", tags=["Admin Rides"])
router.include_router(admin_booking_router, prefix="/admin", tags=["Admin Booking Management"])
router.include_router(admin_dispatch_router, prefix="/admin", tags=["Admin Dispatch Center"])
router.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
router.include_router(driver_router, prefix="/driver", tags=["Driver Rides"])
router.include_router(rating_router, tags=["Ratings"])
router.include_router(recurring_router, prefix="/recurring", tags=["Recurring Rides"])
router.include_router(safety_router, tags=["Safety"])

# Safety & Incidents endpoints
router.include_router(admin_incident_router, prefix="/admin", tags=["Admin Incidents"])
router.include_router(admin_alert_router, prefix="/admin", tags=["Admin Safety Alerts"])
router.include_router(admin_investigation_router, prefix="/admin", tags=["Admin Investigations"])
router.include_router(admin_discipline_router, prefix="/admin", tags=["Admin Disciplinary Actions"])
