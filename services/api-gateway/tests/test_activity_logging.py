"""Only successful admin mutations become activity-log entries."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from starlette.datastructures import Headers

from app.routes.activity_map import classify, extract_entity_id
from app.routes.proxy import _maybe_log_activity


def _request(method: str, forwarded: str = "203.0.113.9, 10.0.0.1"):
    return SimpleNamespace(
        method=method,
        headers=Headers(raw=[(b"x-forwarded-for", forwarded.encode())]),
        client=SimpleNamespace(host="10.0.0.1"),
    )


ADMIN = SimpleNamespace(id="admin-uuid", role="admin", email="admin@example.com")
RIDER = SimpleNamespace(id="rider-uuid", role="rider", email="rider@example.com")


@pytest.mark.parametrize(
    "method,status,claims,should_log",
    [
        ("PUT", 200, ADMIN, True),
        ("POST", 201, ADMIN, True),
        ("DELETE", 204, ADMIN, True),
        ("GET", 200, ADMIN, False),      # reads are not activity
        ("PUT", 403, ADMIN, False),      # rejected calls changed nothing
        ("PUT", 500, ADMIN, False),
        ("PUT", 200, RIDER, False),      # non-admin
        ("PUT", 200, None, False),       # unauthenticated/public route
    ],
)
def test_activity_logged_only_for_successful_admin_mutations(
    method, status, claims, should_log
):
    with patch("app.routes.proxy.emit") as emit:
        _maybe_log_activity(
            _request(method), "/users/admin/drivers/abc-123-def-4567/suspend",
            status, claims,
        )
    assert emit.called is should_log


def test_logged_entry_shape():
    with patch("app.routes.proxy.emit") as emit:
        _maybe_log_activity(
            _request("PUT"), "/users/admin/drivers/abc-123-def-4567/suspend",
            200, ADMIN,
        )
    entry = emit.call_args.args[0]
    assert entry["admin_id"] == "admin-uuid"
    assert entry["admin_email"] == "admin@example.com"
    assert entry["action_title"] == "Driver suspended"
    assert entry["category"] == "Driver"
    assert entry["severity"] == "warning"
    assert entry["target_entity_id"] == "abc-123-def-4567"
    assert entry["target_entity_type"] == "users"
    # First hop of X-Forwarded-For is the real client.
    assert entry["ip_address"] == "203.0.113.9"


def test_logging_failure_never_propagates():
    with patch("app.routes.proxy.emit", side_effect=RuntimeError("boom")):
        _maybe_log_activity(_request("PUT"), "/users/admin/x", 200, ADMIN)


def test_unmatched_admin_route_still_gets_a_readable_entry():
    title, category, severity = classify("POST", "/rides/admin/some-new-thing")
    assert title == "Some new thing created"
    assert category == "Booking"
    assert severity == "info"


def test_extract_entity_id_ignores_resource_names():
    assert extract_entity_id("/users/admin/drivers/suspend") is None
    assert (
        extract_entity_id("/rides/admin/bookings/550e8400-e29b-41d4-a716-446655440000")
        == "550e8400-e29b-41d4-a716-446655440000"
    )
