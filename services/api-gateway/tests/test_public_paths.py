"""Regression guards for gateway auth bypass.

`_is_public_path` used to match with a bare `startswith`, which made
/auth/admin/login-history public (it starts with /auth/admin/login), so the
gateway skipped JWT validation and never set the X-User-* headers the
downstream require_role guard reads. Login History 401'd for every admin,
and the route leaked admin emails/IPs to anyone spoofing a role header.
"""

import pytest

from app.routes.proxy import _STRIPPED_REQUEST_HEADERS, _is_public_path


@pytest.mark.parametrize(
    "path,expected",
    [
        # The bug: admin login is public, its siblings are not.
        ("/auth/admin/login", True),
        ("/auth/admin/login/", True),
        ("/auth/admin/login-history", False),
        ("/auth/admin/login-history/kpis", False),
        ("/auth/admin/login-history/export", False),
        # Near-misses that must stay protected.
        ("/auth/logout", False),
        ("/auth/admin/activity-logs", False),
        ("/auth/admin/security/settings", False),
        ("/auth/registered-devices", False),
        # Genuinely public, exact.
        ("/auth/login", True),
        ("/auth/register", True),
        ("/payments/webhooks/stripe", True),
        ("/notifications/public/contact", True),
        # Public subtree, by design.
        ("/rides/public", True),
        ("/rides/public/guest-bookings", True),
        ("/rides/public/booking-flow/config", True),
        ("/rides/admin/anything", False),
        # Future-proofing: a child of an exact entry is NOT public.
        ("/payments/fare-estimate", True),
        ("/payments/fare-estimate/abc", False),
        ("/users/public/fleet/apply", True),
        ("/users/public/fleet/apply/123", False),
        # Docs.
        ("/auth/docs", True),
        ("/auth/openapi.json", True),
    ],
)
def test_is_public_path(path: str, expected: bool) -> None:
    assert _is_public_path(path) is expected


def test_identity_headers_are_stripped_from_client_requests() -> None:
    """A client must never be able to supply its own identity headers.

    Starlette lowercases incoming header keys, so a spoofed "x-user-role"
    would sit next to the gateway's own "X-User-Role" on the wire and win
    the downstream case-insensitive .get() lookup.
    """
    for header in ("x-user-id", "x-user-role", "x-user-email", "x-business-id"):
        assert header in _STRIPPED_REQUEST_HEADERS
    assert "x-internal-service" in _STRIPPED_REQUEST_HEADERS
    assert "host" in _STRIPPED_REQUEST_HEADERS
