from fastapi import APIRouter

from app.api.v1.chat_endpoints import router as chat_router
from app.api.v1.notification_endpoints import router as notification_router
from app.api.v1.support_endpoints import router as support_router

router = APIRouter()

router.include_router(chat_router, tags=["Chat"])
router.include_router(notification_router, tags=["Notifications Inbox"])
router.include_router(support_router, tags=["Help & Support"])
