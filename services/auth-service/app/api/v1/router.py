from fastapi import APIRouter

from app.api.v1.auth_endpoints import router as auth_router

router = APIRouter(tags=["Auth"])
router.include_router(auth_router)
