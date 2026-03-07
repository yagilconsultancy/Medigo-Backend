from fastapi import APIRouter

from app.api.v1.auth_endpoints import router as auth_router
from app.api.v1.session_endpoints import router as session_router

router = APIRouter(tags=["Auth"])
router.include_router(auth_router)
router.include_router(session_router)
