from fastapi import APIRouter

from app.api.v1.admin_tracking_endpoints import router as admin_tracking_router
from app.api.v1.test_location_endpoints import router as test_location_router
from app.api.v1.tracking_endpoints import router as tracking_router

router = APIRouter()
router.include_router(admin_tracking_router, prefix="/admin", tags=["Admin Tracking"])
router.include_router(tracking_router, tags=["Tracking"])
router.include_router(test_location_router, prefix="/test", tags=["Testing"])
