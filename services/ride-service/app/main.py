import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.internal_endpoints import router as internal_router
from app.api.v1.router import router as v1_router
from app.config import settings
from app.dependencies import get_broker, get_db, get_publisher, get_session_factory, init_broker, init_db
from app.events.consumers import setup_consumers
from app.services.expiry_service import run_expiry_loop
from mediride_common.health import create_health_router
from mediride_common.logging import setup_logging
from mediride_common.middleware import CorrelationIdMiddleware, register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level=settings.LOG_LEVEL, service_name=settings.SERVICE_NAME)
    await init_db()
    await init_broker()
    await setup_consumers()

    # Start background expiry loop
    expiry_task = asyncio.create_task(
        run_expiry_loop(
            session_factory=get_session_factory(),
            publisher=get_publisher(),
            interval_seconds=settings.EXPIRY_CHECK_INTERVAL_SECONDS,
        )
    )

    yield

    # Cancel the expiry loop
    expiry_task.cancel()
    try:
        await expiry_task
    except asyncio.CancelledError:
        pass

    broker = get_broker()
    if broker:
        await broker.close()


app = FastAPI(
    title="MediRide Ride Service",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/rides/docs",
    openapi_url="/rides/openapi.json",
    redoc_url="/rides/redoc",
    root_path="/api/v1",
)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)

app.include_router(v1_router, prefix="/rides")
app.include_router(internal_router, tags=["Internal"])
app.include_router(create_health_router(get_db=get_db))
