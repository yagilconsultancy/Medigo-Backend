import logging

import httpx
from fastapi import APIRouter, Request, Response

from app.config import settings
from app.middleware.activity_logger import emit
from app.middleware.auth_middleware import validate_jwt_and_get_claims
from app.routes.activity_map import classify, extract_entity_id

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

# Public routes matched EXACTLY (optionally with a trailing slash).
# A new route added *underneath* any of these stays protected unless it is
# also listed here, or its parent is promoted to PUBLIC_PATH_PREFIXES below.
#
# This used to be a single set matched with startswith(), which silently made
# /auth/admin/login-history public because it starts with /auth/admin/login.
PUBLIC_EXACT_PATHS = frozenset({
    "/auth/register",
    "/auth/login",
    "/auth/verify-otp",
    "/auth/refresh",
    "/auth/resend-otp",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/reactivate",  # Driver clicks emailed reactivation link (not logged in); JWT in body
    "/auth/admin/login",  # NOT /auth/admin/login-history - that is admin-only
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
    # Play Store requires a deletion URL reachable without the app or a login.
    # These three back getmedigo.com/medigo-delete-account; ownership is proven
    # by an emailed OTP, and an admin still reviews every verified request.
    "/users/public/account-deletion/request",
    "/users/public/account-deletion/verify",
    "/users/public/account-deletion/resend-otp",
    "/notifications/public/contact",  # Public contact form submission
})

# Whole subtrees that are public. Every current AND FUTURE path underneath
# these is unauthenticated - only add here when that is genuinely intended.
PUBLIC_PATH_PREFIXES = (
    "/rides/public/",  # Public guest booking & booking flow endpoints
)

_DOC_SUFFIXES = ("/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect")

# Identity headers the gateway derives from the validated JWT. Anything a
# client sends under these names is attacker-controlled and must be dropped
# before proxying: Starlette lowercases incoming header keys, so a spoofed
# "x-user-role" would otherwise sit alongside the gateway's own "X-User-Role"
# on the wire, and downstream .get() returns the *first* match - the spoof.
_STRIPPED_REQUEST_HEADERS = frozenset({
    "host",
    "x-user-id",
    "x-user-role",
    "x-user-email",
    "x-business-id",
    "x-internal-service",
})


def _get_service_url(path: str) -> tuple[str, str] | None:
    """Determine which service to proxy to based on path."""
    for prefix, url in SERVICE_MAP.items():
        if path.startswith(prefix):
            # Forward the full path to the downstream service
            return url, path
    return None


def _is_public_path(path: str) -> bool:
    """Public iff an exact match, a documented subtree, or a docs endpoint."""
    if path.endswith(_DOC_SUFFIXES):
        return True
    if (path.rstrip("/") or "/") in PUBLIC_EXACT_PATHS:
        return True
    return any(
        path.startswith(prefix) or path == prefix.rstrip("/")
        for prefix in PUBLIC_PATH_PREFIXES
    )


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

    # Build headers to forward, dropping any client-supplied identity headers
    # so they can never survive alongside (and outrank) the gateway's own.
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _STRIPPED_REQUEST_HEADERS
    }

    # Authenticate if not a public path
    claims = None
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

        _maybe_log_activity(request, full_path, response.status_code, claims)

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


def _maybe_log_activity(
    request: Request, path: str, status_code: int, claims
) -> None:
    """Record successful admin mutations. Never raises."""
    if not settings.ACTIVITY_LOG_ENABLED:
        return
    if request.method == "GET" or status_code >= 400:
        return
    if claims is None or claims.role != "admin":
        return

    try:
        title, category, severity = classify(request.method, path)
        entity_type = path.strip("/").split("/")[0] or None
        forwarded = request.headers.get("x-forwarded-for", "")
        ip_address = forwarded.split(",")[0].strip() or (
            request.client.host if request.client else None
        )

        emit(
            {
                "admin_id": str(claims.id),
                "admin_name": claims.email or "Admin",
                "admin_email": claims.email or "",
                "action_title": title,
                "action_description": f"{request.method} {path}",
                "category": category,
                "severity": severity,
                "target_entity_id": extract_entity_id(path),
                "target_entity_type": entity_type,
                "ip_address": ip_address,
            }
        )
    except Exception:  # activity logging must never break the response
        logger.warning("Failed to queue activity log", exc_info=True)
