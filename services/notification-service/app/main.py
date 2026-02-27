from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.events.consumers import setup_consumers
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.logging import setup_logging
from mediride_common.middleware import CorrelationIdMiddleware, register_error_handlers

_broker: RabbitMQBroker | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _broker
    setup_logging(level=settings.LOG_LEVEL, service_name=settings.SERVICE_NAME)
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


@app.get("/health/live")
async def health_live():
    return {"status": "alive", "service": "notification-service"}
