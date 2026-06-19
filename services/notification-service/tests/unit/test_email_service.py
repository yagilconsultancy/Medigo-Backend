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
    assert _send_calls[0]["message"]["Subject"] == "MediGo - Fleet Application Received"
