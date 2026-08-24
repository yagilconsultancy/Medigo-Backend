"""Maps an admin HTTP request to a human-readable activity-log entry.

The gateway sees requests, not domain events, so titles are derived from
method+path. A curated rule wins when it matches; everything else falls back
to a generic per-service entry so coverage is complete from day one.

`category` values must match the BackOffice `categoryStyleMap` keys
(ActivityLogsPage) or the row renders with the default style:
Admin, Fleet, Driver, Finance, Support, Settings, Dispatch, Notification,
Safety, Booking.
"""

import re

# (compiled pattern, method or "*", title, category, severity)
_RULES: list[tuple[re.Pattern[str], str, str, str, str]] = [
    (p, m, t, c, s)
    for p, m, t, c, s in [
        (re.compile(r"^/auth/admin/security/settings/?$"), "PUT",
         "Security settings updated", "Settings", "critical"),
        (re.compile(r"^/users/admin/roles"), "*",
         "Role permissions changed", "Admin", "critical"),
        (re.compile(r"^/users/admin/drivers/[^/]+/approve/?$"), "*",
         "Driver approved", "Driver", "info"),
        (re.compile(r"^/users/admin/drivers/[^/]+/suspend/?$"), "*",
         "Driver suspended", "Driver", "warning"),
        (re.compile(r"^/users/admin/drivers/[^/]+/reactivate/?$"), "*",
         "Driver reactivated", "Driver", "info"),
        (re.compile(r"^/users/admin/riders/[^/]+/suspend/?$"), "*",
         "Rider suspended", "Admin", "warning"),
        (re.compile(r"^/users/admin/fleets"), "*",
         "Fleet updated", "Fleet", "info"),
        (re.compile(r"^/payments/admin/refunds"), "*",
         "Refund processed", "Finance", "warning"),
        (re.compile(r"^/payments/admin/payouts"), "*",
         "Payout processed", "Finance", "warning"),
        (re.compile(r"^/payments/(admin/)?pricing"), "*",
         "Pricing configuration changed", "Finance", "warning"),
        (re.compile(r"^/rides/admin/bookings/[^/]+/cancel/?$"), "*",
         "Booking cancelled", "Booking", "warning"),
        (re.compile(r"^/rides/admin/bookings/[^/]+/assign-driver/?$"), "*",
         "Driver assigned to booking", "Dispatch", "info"),
        (re.compile(r"^/rides/admin/bookings"), "*",
         "Booking updated", "Booking", "info"),
        (re.compile(r"^/rides/admin/dispatch"), "*",
         "Dispatch action", "Dispatch", "info"),
        (re.compile(r"^/rides/admin/incidents"), "*",
         "Incident updated", "Safety", "warning"),
        (re.compile(r"^/notifications/admin/broadcasts"), "*",
         "Broadcast sent", "Notification", "info"),
        (re.compile(r"^/notifications/admin/support"), "*",
         "Support ticket updated", "Support", "info"),
        (re.compile(r"^/auth/admin/register/?$"), "*",
         "Admin account created", "Admin", "critical"),
    ]
]

# Fallback category by owning service.
_CATEGORY_BY_SERVICE = {
    "/auth": "Settings",
    "/users": "Admin",
    "/rides": "Booking",
    "/payments": "Finance",
    "/notifications": "Notification",
    "/tracking": "Dispatch",
    "/locations": "Settings",
}

_METHOD_VERB = {
    "POST": "created",
    "PUT": "updated",
    "PATCH": "updated",
    "DELETE": "deleted",
}

# Path segments that are identifiers rather than resource names.
_ID_LIKE = re.compile(
    r"^([0-9a-fA-F-]{16,}|\d+)$"
)


def extract_entity_id(path: str) -> str | None:
    """Last id-looking segment of the path, if any."""
    for segment in reversed(path.strip("/").split("/")):
        if _ID_LIKE.match(segment):
            return segment
    return None


def _service_prefix(path: str) -> str | None:
    for prefix in _CATEGORY_BY_SERVICE:
        if path.startswith(prefix):
            return prefix
    return None


def classify(method: str, path: str) -> tuple[str, str, str]:
    """Return (action_title, category, severity) for an admin request."""
    for pattern, rule_method, title, category, severity in _RULES:
        if (rule_method == "*" or rule_method == method) and pattern.match(path):
            # A destructive call is never routine, even if the rule it matched
            # was written for the resource's ordinary update path.
            if method == "DELETE" and severity == "info":
                severity = "warning"
            return title, category, severity

    prefix = _service_prefix(path)
    category = _CATEGORY_BY_SERVICE.get(prefix or "", "Admin")

    # Best-effort readable name: last non-id segment of the path.
    resource = None
    for segment in reversed(path.strip("/").split("/")):
        if segment and not _ID_LIKE.match(segment):
            resource = segment.replace("-", " ").replace("_", " ")
            break

    verb = _METHOD_VERB.get(method, method.lower())
    title = f"{resource.capitalize()} {verb}" if resource else f"{method} {path}"
    severity = "warning" if method == "DELETE" else "info"
    return title, category, severity
