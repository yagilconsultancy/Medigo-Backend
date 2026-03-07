from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.config import settings
from app.dependencies import get_db, init_db
from app.events.consumers import setup_consumers
from app.realtime.socket_manager import sio
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.health import create_health_router
from mediride_common.logging import setup_logging
from mediride_common.middleware import CorrelationIdMiddleware, register_error_handlers

_broker: RabbitMQBroker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _broker
    setup_logging(level=settings.LOG_LEVEL, service_name=settings.SERVICE_NAME)
    await init_db()
    _broker = RabbitMQBroker(settings.RABBITMQ_URL)
    await _broker.connect()
    await setup_consumers(_broker)
    yield
    if _broker:
        await _broker.close()


app = FastAPI(
    title="MediRide Notification Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)

app.include_router(v1_router, prefix="/notifications")
app.include_router(create_health_router(get_db=get_db))

# Wrap FastAPI app with Socket.IO for real-time chat
socket_app = socketio.ASGIApp(sio, app)
