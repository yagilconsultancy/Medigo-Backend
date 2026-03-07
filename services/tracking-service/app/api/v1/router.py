from fastapi import APIRouter

from app.api.v1.tracking_endpoints import router as tracking_router

router = APIRouter()
router.include_router(tracking_router, tags=["Tracking"])
