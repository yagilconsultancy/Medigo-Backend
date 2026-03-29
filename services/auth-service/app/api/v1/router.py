from fastapi import APIRouter

from app.api.v1.admin_activity_endpoints import router as admin_activity_router
from app.api.v1.admin_login_history_endpoints import router as admin_login_history_router
from app.api.v1.admin_security_endpoints import router as admin_security_router
from app.api.v1.auth_endpoints import router as auth_router
from app.api.v1.session_endpoints import router as session_router

router = APIRouter(tags=["Auth"])
router.include_router(auth_router)
router.include_router(session_router)
router.include_router(admin_activity_router, prefix="/admin")
router.include_router(admin_login_history_router, prefix="/admin")
router.include_router(admin_security_router, prefix="/admin")
