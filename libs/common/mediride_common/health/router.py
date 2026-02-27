from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def create_health_router(
    get_db=None,
    check_rabbitmq=None,
) -> APIRouter:
    router = APIRouter(tags=["Health"])

    @router.get("/health/live")
    async def liveness():
        return {"status": "alive"}

    @router.get("/health/ready")
    async def readiness():
        checks = {}

        if get_db:
            try:
                async for session in get_db():
                    await session.execute(text("SELECT 1"))
                    checks["database"] = True
            except Exception:
                checks["database"] = False

        if check_rabbitmq:
            try:
                checks["rabbitmq"] = await check_rabbitmq()
            except Exception:
                checks["rabbitmq"] = False

        all_healthy = all(checks.values()) if checks else True
        status_code = 200 if all_healthy else 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if all_healthy else "not_ready",
                "checks": checks,
            },
        )

    return router
