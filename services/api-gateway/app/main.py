import socketio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.activity_logger import (
    start_activity_logger,
    stop_activity_logger,
)
from app.realtime.socket_proxy import sio as socket_sio
from app.routes.docs import router as docs_router
from app.routes.proxy import router as proxy_router
from mediride_common.logging import setup_logging
from mediride_common.middleware import CorrelationIdMiddleware, register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level=settings.LOG_LEVEL, service_name="api-gateway")
    if settings.ACTIVITY_LOG_ENABLED:
        await start_activity_logger()
    try:
        yield
    finally:
        if settings.ACTIVITY_LOG_ENABLED:
            await stop_activity_logger()


fastapi_app = FastAPI(
    title="MediRide API Gateway",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware
fastapi_app.add_middleware(CorrelationIdMiddleware)


# Error handlers
register_error_handlers(fastapi_app)

# Routes
fastapi_app.include_router(docs_router, prefix="/docs")
fastapi_app.include_router(proxy_router, prefix="/api/v1")


@fastapi_app.get("/health/live")
async def health_live():
    return {"status": "alive", "service": "api-gateway"}


app = socketio.ASGIApp(
    socket_sio,
    other_asgi_app=fastapi_app,
    socketio_path="api/v1/ws/socket.io",
)
