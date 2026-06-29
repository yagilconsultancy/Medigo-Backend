import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from mediride_common.exceptions import MediRideError
from mediride_common.schemas.responses import ErrorResponse

logger = logging.getLogger(__name__)


def _sanitize_errors(errors: list) -> list:
    """Make pydantic validation errors JSON-serializable by converting
    non-serializable objects (e.g. ValueError) in 'ctx' to strings."""
    sanitized = []
    for err in errors:
        err = dict(err)
        if "ctx" in err and isinstance(err["ctx"], dict):
            err["ctx"] = {
                k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                for k, v in err["ctx"].items()
            }
        sanitized.append(err)
    return sanitized


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        body = await request.body()
        logger.warning(
            "Validation error on %s %s | body=%s | errors=%s",
            request.method,
            request.url.path,
            body.decode(errors="replace"),
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                message="Validation error",
                error_code="VALIDATION_ERROR",
                details=_sanitize_errors(exc.errors()),
            ).model_dump(),
        )

    @app.exception_handler(MediRideError)
    async def mediride_error_handler(request: Request, exc: MediRideError):
        logger.warning(
            f"{exc.error_code}: {exc.message}",
            extra={"details": exc.details},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                message=exc.message,
                error_code=exc.error_code,
                details=exc.details,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                message="An unexpected error occurred",
                error_code="INTERNAL_ERROR",
            ).model_dump(),
        )
