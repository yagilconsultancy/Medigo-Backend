from fastapi import APIRouter

from app.api.v1.admin_broadcast_endpoints import router as admin_broadcast_router
from app.api.v1.admin_contact_endpoints import router as admin_contact_router
from app.api.v1.admin_notification_endpoints import router as admin_notification_router
from app.api.v1.admin_support_endpoints import router as admin_support_router
from app.api.v1.chat_endpoints import router as chat_router
from app.api.v1.notification_endpoints import router as notification_router
from app.api.v1.public_contact_endpoints import router as public_contact_router
from app.api.v1.push_token_endpoints import router as push_token_router
from app.api.v1.support_endpoints import router as support_router

router = APIRouter()

router.include_router(chat_router, tags=["Chat"])
router.include_router(notification_router, tags=["Notifications Inbox"])
router.include_router(push_token_router, tags=["Push Tokens"])
router.include_router(support_router, tags=["Help & Support"])
router.include_router(public_contact_router, prefix="/public", tags=["Public Contact"])

# Admin endpoints
router.include_router(admin_broadcast_router, prefix="/admin", tags=["Admin Broadcasts"])
router.include_router(admin_notification_router, prefix="/admin", tags=["Admin Notifications"])
router.include_router(admin_support_router, prefix="/admin", tags=["Admin Support Center"])
router.include_router(admin_contact_router, prefix="/admin", tags=["Admin Contact Logs"])
