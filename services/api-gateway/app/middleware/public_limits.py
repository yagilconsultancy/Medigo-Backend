"""Per-visitor limits for the public endpoints that anyone on the internet can call.

nginx already caps the raw request rate, but it treats a sign-in the same as a
page load. These limits are stricter and per kind of action, so a flood of
"send me a code" requests (which cost real email and SMS money) or guest
bookings stops long before it becomes a problem.

Each rule belongs to a group. All paths in a group share one counter per
visitor, so alternating between two endpoints does not double the allowance.
The counter lives in Redis (shared by every gateway container) and the check
fails open: if Redis is unreachable the request goes through, exactly like the
sign-out check does.
"""

import logging

from fastapi import Request, Response

from app.config import settings
from app.middleware.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

# group name -> (max requests, window in seconds)
GROUP_LIMITS: dict[str, tuple[int, int]] = {
    "login": (30, 300),
    "register": (10, 600),
    "send_code": (5, 600),
    "check_code": (20, 600),
    "public_form": (10, 600),
    "fleet_apply": (5, 3600),
    "maps_lookup": (120, 60),
}

# (HTTP method, exact path without trailing slash) -> group name
_RULES: dict[tuple[str, str], str] = {
    ("POST", "/auth/login"): "login",
    ("POST", "/auth/admin/login"): "login",
    ("POST", "/auth/register"): "register",
    ("POST", "/auth/driver/register"): "register",
    ("POST", "/auth/admin/register"): "register",
    # Each of these sends an email or a text message.
    ("POST", "/auth/forgot-password"): "send_code",
    ("POST", "/auth/resend-otp"): "send_code",
    ("POST", "/auth/driver/activation/request-otp"): "send_code",
    ("POST", "/users/public/account-deletion/request"): "send_code",
    ("POST", "/users/public/account-deletion/resend-otp"): "send_code",
    # Each of these checks a code or a link token.
    ("POST", "/auth/verify-otp"): "check_code",
    ("POST", "/auth/reset-password"): "check_code",
    ("POST", "/auth/reactivate"): "check_code",
    ("POST", "/auth/driver/activation/check"): "check_code",
    ("POST", "/auth/driver/activation/complete"): "check_code",
    ("POST", "/auth/admin/verify-invite"): "check_code",
    ("POST", "/auth/driver/verify-invite"): "check_code",
    ("POST", "/users/public/account-deletion/verify"): "check_code",
    # Public forms.
    ("POST", "/rides/public/guest-sessions"): "public_form",
    ("POST", "/notifications/public/contact"): "public_form",
    ("POST", "/users/public/fleet/apply"): "fleet_apply",
    # Public lookups that call the paid maps service.
    ("POST", "/payments/fare-estimate"): "maps_lookup",
    ("POST", "/payments/base-fare-estimate"): "maps_lookup",
    ("GET", "/locations/public/check-address"): "maps_lookup",
}

_TOO_MANY = (
    '{"success": false, "message": "Too many requests. Please wait a few '
    'minutes and try again.", "error_code": "RATE_LIMITED"}'
)


def limit_group_for(method: str, path: str) -> str | None:
    """The rule group for this request, or None if it is not limited."""
    return _RULES.get((method.upper(), path.rstrip("/") or "/"))


def client_ip(request: Request) -> str:
    """The visitor's address as nginx saw it.

    nginx overwrites X-Real-IP with the connecting address, and the gateway
    port is only reachable from the server itself, so a visitor cannot choose
    this value. Without nginx (local development) fall back to the socket.
    """
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


async def enforce_public_limits(request: Request, path: str) -> Response | None:
    """Return a 429 response when this visitor is over the limit, else None."""
    if not settings.RATE_LIMIT_ENABLED:
        return None
    group = limit_group_for(request.method, path)
    if group is None:
        return None

    max_requests, window = GROUP_LIMITS[group]
    allowed = await check_rate_limit(
        f"rl:{group}:{client_ip(request)}",
        max_requests=max_requests,
        window_seconds=window,
    )
    if allowed:
        return None

    logger.warning("Rate limit hit: group=%s ip=%s path=%s", group, client_ip(request), path)
    return Response(
        content=_TOO_MANY,
        status_code=429,
        media_type="application/json",
        headers={"Retry-After": str(window)},
    )
