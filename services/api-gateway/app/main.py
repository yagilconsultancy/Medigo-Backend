from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.proxy import router as proxy_router
from mediride_common.logging import setup_logging
from mediride_common.middleware import CorrelationIdMiddleware, register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(level=settings.LOG_LEVEL, service_name="api-gateway")
    yield


app = FastAPI(
    title="MediRide API Gateway",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware
app.add_middleware(CorrelationIdMiddleware)

# Error handlers
register_error_handlers(app)

# Routes
app.include_router(proxy_router, prefix="/api/v1")


@app.get("/health/live")
async def health_live():
    return {"status": "alive", "service": "api-gateway"}
