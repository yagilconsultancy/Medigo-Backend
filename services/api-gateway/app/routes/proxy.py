import logging

import httpx
from fastapi import APIRouter, Request, Response

from app.config import settings
from app.middleware.auth_middleware import validate_jwt_and_get_claims

logger = logging.getLogger(__name__)

router = APIRouter()

# Route mapping: path prefix -> service URL
SERVICE_MAP = {
    "/auth": settings.AUTH_SERVICE_URL,
    "/users": settings.USER_SERVICE_URL,
    "/rides": settings.RIDE_SERVICE_URL,
    "/locations": settings.LOCATION_SERVICE_URL,
    "/payments": settings.PAYMENT_SERVICE_URL,
    "/tracking": settings.TRACKING_SERVICE_URL,
    "/notifications": settings.NOTIFICATION_SERVICE_URL,
}

# Public routes that don't require authentication
PUBLIC_PATHS = {
    "/auth/register",
    "/auth/login",
    "/auth/verify-otp",
    "/auth/refresh",
    "/auth/resend-otp",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/admin/login",
    "/auth/admin/verify-invite",
    "/auth/admin/register",
    "/auth/driver/verify-invite",
    "/auth/driver/register",
    "/payments/webhooks/stripe",
    "/payments/fare-estimate",  # Public fare estimates for riders
    "/payments/base-fare-estimate",  # Public base fare estimates for guests
    "/payments/guest/payment-intent",  # Guest payment intent (uses session_id instead of JWT)
    "/tracking/test/simulate-location",  # Public test endpoint for simulating driver GPS
    "/locations/public/check-address",  # Public address validation
    "/users/public/fleet/apply",  # Public fleet partner application
    "/notifications/public/contact",  # Public contact form submission
    "/rides/public",  # Public guest booking & booking flow endpoints
}


def _get_service_url(path: str) -> tuple[str, str] | None:
    """Determine which service to proxy to based on path."""
    for prefix, url in SERVICE_MAP.items():
        if path.startswith(prefix):
            # Forward the full path to the downstream service
            return url, path
    return None


def _is_public_path(path: str) -> bool:
    """Check if the path is publicly accessible without auth."""
    # Allow docs endpoints for all services
    if path.endswith(("/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect")):
        return True
    for public_path in PUBLIC_PATHS:
        if path.startswith(public_path):
            return True
    return False


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_request(request: Request, path: str):
    """Proxy incoming requests to downstream services."""
    full_path = f"/{path}"

    # Determine target service
    result = _get_service_url(full_path)
    if not result:
        return Response(
            content='{"success": false, "message": "Route not found", "error_code": "NOT_FOUND"}',
            status_code=404,
            media_type="application/json",
        )

    service_url, downstream_path = result

    # Build headers to forward
    headers = dict(request.headers)
    headers.pop("host", None)

    # Authenticate if not a public path
    if not _is_public_path(full_path):
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response(
                content='{"success": false, "message": "Authorization header required", "error_code": "AUTHENTICATION_ERROR"}',
                status_code=401,
                media_type="application/json",
            )

        token = auth_header.split(" ", 1)[1]
        claims = validate_jwt_and_get_claims(token)
        if not claims:
            return Response(
                content='{"success": false, "message": "Invalid or expired token", "error_code": "AUTHENTICATION_ERROR"}',
                status_code=401,
                media_type="application/json",
            )

        # Enrich headers with user claims
        headers["X-User-ID"] = str(claims.id)
        headers["X-User-Role"] = claims.role
        headers["X-User-Email"] = claims.email or ""
        if claims.business_id:
            headers["X-Business-ID"] = str(claims.business_id)

    # Forward correlation ID
    correlation_id = getattr(request.state, "correlation_id", "")
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    # Build downstream URL
    target_url = f"{service_url}{downstream_path}"

    # Add query parameters
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Read request body
    body = await request.body()

    # Proxy the request
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type"),
        )
    except httpx.ConnectError:
        logger.error(f"Failed to connect to {service_url}")
        return Response(
            content='{"success": false, "message": "Service unavailable", "error_code": "SERVICE_UNAVAILABLE"}',
            status_code=503,
            media_type="application/json",
        )
    except httpx.TimeoutException:
        logger.error(f"Timeout connecting to {service_url}")
        return Response(
            content='{"success": false, "message": "Service timeout", "error_code": "TIMEOUT"}',
            status_code=504,
            media_type="application/json",
        )
