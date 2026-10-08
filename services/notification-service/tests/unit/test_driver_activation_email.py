"""The driver welcome email carries the code and never a password."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.events import consumers
from app.services import email_service
from mediride_common.events.constants import RoutingKeys


@pytest.mark.asyncio
async def test_activation_email_has_code_and_no_password(monkeypatch):
    sent = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", sent)
    assert await email_service.send_driver_activation_email("d@example.com", "482913")
    to, subject, html = sent.await_args.args
    assert to == "d@example.com"
    assert "482913" in html
    assert "password:" not in html.lower()
    assert "MediRide2026" not in html


@pytest.mark.asyncio
async def test_consumer_routes_driver_activation_purpose(monkeypatch):
    activation = AsyncMock(return_value=True)
    generic = AsyncMock(return_value=True)
    monkeypatch.setattr(consumers, "send_driver_activation_email", activation)
    monkeypatch.setattr(consumers, "send_otp_email", generic)

    consumer = consumers.AuthEventConsumer.__new__(consumers.AuthEventConsumer)

    def envelope(purpose):
        env = MagicMock()
        env.event_type = RoutingKeys.USER_OTP_REQUESTED
        env.payload = {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "purpose": purpose,
            "channel": "email",
            "otp_code": "123456",
            "email": "d@example.com",
        }
        return env

    await consumer.handle(envelope("driver_activation"))
    activation.assert_awaited_once()
    generic.assert_not_awaited()

    await consumer.handle(envelope("registration"))
    generic.assert_awaited_once()
