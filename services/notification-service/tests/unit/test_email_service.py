import os
import sys
import types

import pytest

from mediride_common.exceptions import ServiceUnavailableError

os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "development"


class _DummyTemplateEnv:
    def __init__(self, *args, **kwargs):
        pass

    def get_template(self, *args, **kwargs):
        raise RuntimeError("template loading is not needed in this test")


_send_calls = []


async def _dummy_send(message, **kwargs):
    _send_calls.append({"message": message, **kwargs})


sys.modules["aiosmtplib"] = types.SimpleNamespace(send=_dummy_send)
sys.modules["jinja2"] = types.SimpleNamespace(
    Environment=_DummyTemplateEnv,
    FileSystemLoader=lambda *args, **kwargs: None,
    select_autoescape=lambda *args, **kwargs: None,
)

from app.services import email_service


@pytest.fixture(autouse=True)
def _reset_settings(monkeypatch):
    _send_calls.clear()
    monkeypatch.setattr(email_service.aiosmtplib, "send", _dummy_send, raising=False)
    monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.mailgun.org")
    monkeypatch.setattr(email_service.settings, "SMTP_PORT", 587)
    monkeypatch.setattr(email_service.settings, "SMTP_USERNAME", "noreply@mail.getmedigo.com")
    monkeypatch.setattr(email_service.settings, "SMTP_PASSWORD", "secret")
    monkeypatch.setattr(email_service.settings, "SMTP_STARTTLS", True)
    monkeypatch.setattr(email_service.settings, "SMTP_USE_TLS", False)
    monkeypatch.setattr(email_service.settings, "SMTP_TIMEOUT_SECONDS", 30)
    monkeypatch.setattr(email_service.settings, "EMAIL_FROM", "noreply@mail.getmedigo.com")
    monkeypatch.setattr(email_service.settings, "PARTNERS_EMAIL_FROM", "partners@mail.getmedigo.com")
    monkeypatch.setattr(email_service.settings, "PARTNERS_EMAIL_REPLY_TO", "partners@mail.getmedigo.com")
    monkeypatch.setattr(email_service.settings, "PARTNERS_SMTP_USERNAME", "partners@mail.getmedigo.com")
    monkeypatch.setattr(email_service.settings, "PARTNERS_SMTP_PASSWORD", "partners-secret")
    monkeypatch.setattr(email_service.settings, "BACKOFFICE_URL", "https://backoffice.getmedigo.com")


@pytest.mark.asyncio
async def test_send_email_uses_starttls_for_submission_port():
    sent = await email_service.send_email(
        to="user@example.com",
        subject="Test Email",
        html_body="<p>Hello</p>",
    )

    assert sent is True
    assert len(_send_calls) == 1
    assert _send_calls[0]["hostname"] == "smtp.mailgun.org"
    assert _send_calls[0]["port"] == 587
    assert _send_calls[0]["start_tls"] is True
    assert _send_calls[0]["use_tls"] is False


@pytest.mark.asyncio
async def test_send_email_requires_complete_smtp_configuration(monkeypatch):
    monkeypatch.setattr(email_service.settings, "SMTP_PASSWORD", "")

    with pytest.raises(ServiceUnavailableError):
        await email_service.send_email(
            to="user@example.com",
            subject="Test Email",
            html_body="<p>Hello</p>",
        )


@pytest.mark.asyncio
async def test_send_payment_receipt_email_formats_receipt_contents():
    sent = await email_service.send_payment_receipt_email(
        to="rider@example.com",
        name="Rider One",
        receipt={
            "trip_number": "TRIP-ABC123",
            "currency": "CAD",
            "total_fare": 24.5,
            "ride_date": "2026-05-11T09:00:00Z",
            "pickup_address": "1 Main St",
            "destination_address": "2 Elm St",
            "payment_method_type": "visa",
            "payment_method_last_four": "4242",
            "paid_at": "2026-05-11T09:45:00Z",
        },
    )

    assert sent is True
    assert len(_send_calls) == 1
    assert _send_calls[0]["message"]["To"] == "rider@example.com"
    assert "Receipt for TRIP-ABC123" in _send_calls[0]["message"]["Subject"]


@pytest.mark.asyncio
async def test_send_fleet_application_received_email_uses_partners_sender():
    sent = await email_service.send_fleet_application_received_email(
        to="fleet@example.com",
        company_name="Acme Fleet",
    )

    assert sent is True
    assert len(_send_calls) == 1
    assert _send_calls[0]["message"]["To"] == "fleet@example.com"
    assert _send_calls[0]["message"]["From"] == "partners@mail.getmedigo.com"
    assert _send_calls[0]["message"]["Reply-To"] == "partners@mail.getmedigo.com"
    assert _send_calls[0]["username"] == "partners@mail.getmedigo.com"
    assert _send_calls[0]["password"] == "partners-secret"
    assert _send_calls[0]["message"]["Subject"] == "MediGo - Fleet Application Received"


def _html_body(message):
    for part in message.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode()
    raise AssertionError("no text/html part in message")


def _booking(**overrides):
    booking = {
        "ride_id": "3f1c9a2e-77b4-4d19-9c33-8a5e1b2d4f60",
        "rider_id": "aa11bb22-cc33-dd44-ee55-ff6677889900",
        "ride_type": "wheelchair",
        "pickup_address": "42 Maple Grove Rd",
        "destination_address": "Toronto General Hospital",
        "scheduled_at": "2026-09-11T13:00:00+00:00",
        "estimated_cost": 124.5,
        "currency": "CAD",
        "passenger_first_name": "Margaret",
        "passenger_last_name": "Chen",
        "mobility_level": "wheelchair",
        "assistance_level": "moderate",
        "booked_by_name": "David Chen",
    }
    booking.update(overrides)
    return booking


@pytest.mark.asyncio
async def test_send_admin_ride_booking_email_addresses_all_recipients():
    sent = await email_service.send_admin_ride_booking_email(
        to=["admin@getmedigo.com", "ops@getmedigo.com"],
        booking=_booking(),
    )

    assert sent is True
    assert len(_send_calls) == 1
    message = _send_calls[0]["message"]
    assert message["To"] == "admin@getmedigo.com, ops@getmedigo.com"
    assert "BK-3F1C9A2E" in message["Subject"]


@pytest.mark.asyncio
async def test_send_admin_ride_booking_email_skips_when_no_recipients():
    sent = await email_service.send_admin_ride_booking_email(to=[], booking=_booking())

    assert sent is False
    assert _send_calls == []


@pytest.mark.asyncio
async def test_send_admin_ride_booking_email_never_exposes_raw_values():
    """The alert is read by non-technical staff: no enum slugs, UUIDs or 'None'."""
    await email_service.send_admin_ride_booking_email(
        to=["admin@getmedigo.com"],
        booking=_booking(estimated_cost=None, mobility_level=None),
    )

    body = _html_body(_send_calls[0]["message"])
    assert "None" not in body
    assert "3f1c9a2e-77b4-4d19-9c33-8a5e1b2d4f60" not in body
    assert "BK-3F1C9A2E" in body
    assert "Not yet estimated" in body


def test_humanize_falls_back_to_readable_text_for_unknown_values():
    assert email_service._humanize("wheelchair", email_service._MOBILITY_LABELS) == "Uses a wheelchair"
    assert email_service._humanize("some_new_value", email_service._MOBILITY_LABELS) == "Some new value"
    assert email_service._humanize(None, email_service._MOBILITY_LABELS) == "Not specified"


def test_format_duration_reads_as_plain_english():
    assert email_service._format_duration(45) == "about 45 min"
    assert email_service._format_duration(75) == "about 1 hr 15 min"
    assert email_service._format_duration(120) == "about 2 hr"
    assert email_service._format_duration(None) is None


def test_urgent_note_flags_imminent_and_past_pickups():
    from datetime import UTC, datetime, timedelta

    soon = datetime.now(UTC) + timedelta(hours=3, minutes=1)
    later = datetime.now(UTC) + timedelta(days=4)
    past = datetime.now(UTC) - timedelta(hours=1)

    assert "about 3 hours" in email_service._urgent_note(soon)
    assert email_service._urgent_note(later) is None
    assert "already passed" in email_service._urgent_note(past)



@pytest.mark.asyncio
async def test_partners_email_never_mixes_username_and_password(monkeypatch):
    """A partners username without its password must not borrow the default password.

    Mixing them authenticates as partners@ with noreply@'s password; the SMTP
    server rejects the login and drops the connection mid-AUTH.
    """
    monkeypatch.setattr(email_service.settings, "PARTNERS_SMTP_USERNAME", "partners@mail.getmedigo.com")
    monkeypatch.setattr(email_service.settings, "PARTNERS_SMTP_PASSWORD", "")

    await email_service.send_fleet_application_received_email(
        to="fleet@example.com", company_name="Acme Fleet"
    )

    call = _send_calls[0]
    assert call["username"] == "noreply@mail.getmedigo.com"
    assert call["password"] == "secret"


@pytest.mark.asyncio
async def test_partners_email_uses_partners_login_when_fully_configured():
    await email_service.send_fleet_application_received_email(
        to="fleet@example.com", company_name="Acme Fleet"
    )

    call = _send_calls[0]
    assert call["username"] == "partners@mail.getmedigo.com"
    assert call["password"] == "partners-secret"
