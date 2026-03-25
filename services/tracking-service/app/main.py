from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.config import settings
from app.dependencies import get_broker, get_db, init_broker, init_db, init_redis
from app.events.consumers import setup_consumers
from app.realtime.socket_manager import sio
from mediride_common.health import create_health_router
from mediride_common.logging import setup_logging
from mediride_common.middleware import CorrelationIdMiddleware, register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level=settings.LOG_LEVEL, service_name=settings.SERVICE_NAME)
    await init_db()
    await init_broker()
    await init_redis()
    await setup_consumers()
    yield
    broker = get_broker()
    if broker:
        await broker.close()


fastapi_app = FastAPI(
    title="MediRide Tracking Service",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/tracking/docs",
    openapi_url="/tracking/openapi.json",
    redoc_url="/tracking/redoc",
    root_path="/api/v1",
    swagger_ui_parameters={"persistAuthorization": True},
)


def custom_openapi():
    if fastapi_app.openapi_schema:
        return fastapi_app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(title=fastapi_app.title, version=fastapi_app.version, routes=fastapi_app.routes)
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http", "scheme": "bearer", "bearerFormat": "JWT",
    }
    schema["security"] = [{"BearerAuth": []}]
    fastapi_app.openapi_schema = schema
    return schema


fastapi_app.openapi = custom_openapi

fastapi_app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(fastapi_app)

fastapi_app.include_router(v1_router, prefix="/tracking")
fastapi_app.include_router(create_health_router(get_db=get_db))

# Wrap FastAPI app with Socket.IO ASGI app
socket_app = socketio.ASGIApp(sio, fastapi_app)
