from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.config import settings
from app.dependencies import get_broker, get_db, init_db, init_broker
from mediride_common.health import create_health_router
from mediride_common.logging import setup_logging
from mediride_common.middleware import CorrelationIdMiddleware, register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level=settings.LOG_LEVEL, service_name=settings.SERVICE_NAME)
    await init_db()
    await init_broker()
    yield
    broker = get_broker()
    if broker:
        await broker.close()


app = FastAPI(
    title="MediRide Auth Service",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(CorrelationIdMiddleware)

# Error handlers
register_error_handlers(app)

# Routes
app.include_router(v1_router, prefix="/auth")
app.include_router(create_health_router(get_db=get_db))
