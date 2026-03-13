from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.internal_endpoints import router as internal_router
from app.api.v1.router import router as v1_router
from app.config import settings
from app.dependencies import get_broker, get_db, init_broker, init_db, init_gmaps
from mediride_common.health import create_health_router
from mediride_common.logging import setup_logging
from mediride_common.middleware import CorrelationIdMiddleware, register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level=settings.LOG_LEVEL, service_name=settings.SERVICE_NAME)
    await init_db()
    await init_broker()
    init_gmaps()
    yield
    broker = get_broker()
    if broker:
        await broker.close()


app = FastAPI(
    title="MediRide Location Service",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/locations/docs",
    openapi_url="/locations/openapi.json",
    redoc_url="/locations/redoc",
    root_path="/api/v1",
)

app.add_middleware(CorrelationIdMiddleware)
register_error_handlers(app)

app.include_router(v1_router, prefix="/locations")
app.include_router(internal_router, tags=["Internal"])
app.include_router(create_health_router(get_db=get_db))
