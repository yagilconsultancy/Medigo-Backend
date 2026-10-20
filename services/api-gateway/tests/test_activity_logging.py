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


def test_logout_reads_as_signed_out():
    title, category, severity = classify("POST", "/auth/logout")
    assert (title, category, severity) == ("Signed out", "Admin", "info")


def test_booking_actions_have_their_own_titles():
    assert classify("PUT", "/rides/admin/bookings/abc/approve")[0] == "Booking approved"
    assert classify("PUT", "/rides/admin/bookings/abc/decline")[0] == "Booking declined"
    deleted = classify("DELETE", "/rides/admin/bookings/604b884e-0993-45a4-b7c9-bb5b51fa696d")
    assert deleted == ("Booking deleted", "Booking", "warning")
    assert classify("PUT", "/rides/admin/bookings/604b884e-0993-45a4-b7c9-bb5b51fa696d")[0] == "Booking updated"


def test_fallback_titles_are_singular():
    assert classify("DELETE", "/users/admin/drivers/50ae9bad-9ab9-406c-99b5-1609ab928c0e")[0] == "Driver deleted"
    assert classify("POST", "/rides/")[0] == "Ride created"
    assert classify("DELETE", "/users/admin/vehicle-categories/12")[0] == "Vehicle category deleted"
    assert classify("PUT", "/rides/admin/status")[0] == "Status updated"


def test_fleet_application_actions_have_their_own_titles():
    app = "/users/admin/fleet/applications/396c486e-9cb2-4100-bbad-5cced2048655"
    assert classify("PUT", app + "/approve") == ("Fleet application approved", "Fleet", "info")
    assert classify("PUT", app + "/reject") == ("Fleet application rejected", "Fleet", "warning")
    assert classify("PUT", app + "/request-info")[0] == "More information requested"
    assert classify("DELETE", app)[0] == "Fleet application deleted"
    company = "/users/admin/fleet/companies/abc"
    assert classify("PUT", company + "/status") == ("Fleet company status changed", "Fleet", "warning")
