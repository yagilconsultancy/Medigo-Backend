import os
import sys
import types
from uuid import uuid4

import pytest

os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "development"


class _DummyTemplateEnv:
    def __init__(self, *args, **kwargs):
        pass

    def get_template(self, *args, **kwargs):
        raise RuntimeError("template loading is not needed in this test")


class _DummyMessage:
    def __init__(self, *args, **kwargs):
        pass


class _DummyDeliveryMode:
    PERSISTENT = 2


class _DummyExchangeType:
    TOPIC = "topic"
    FANOUT = "fanout"


sys.modules.setdefault("aiosmtplib", types.SimpleNamespace(send=None))
sys.modules.setdefault(
    "jinja2",
    types.SimpleNamespace(
        Environment=_DummyTemplateEnv,
        FileSystemLoader=lambda *args, **kwargs: None,
        select_autoescape=lambda *args, **kwargs: None,
    ),
)
sys.modules.setdefault(
    "aio_pika",
    types.SimpleNamespace(
        connect_robust=None,
        DeliveryMode=_DummyDeliveryMode,
        ExchangeType=_DummyExchangeType,
        Message=_DummyMessage,
    ),
)
sys.modules.setdefault(
    "aio_pika.abc",
    types.SimpleNamespace(
        AbstractChannel=object,
        AbstractConnection=object,
        AbstractExchange=object,
        AbstractIncomingMessage=object,
    ),
)

from app.events import consumers
from mediride_common.events.constants import RoutingKeys
from mediride_common.events.schemas import EventEnvelope, PaymentCompletedPayload
from mediride_common.schemas.enums import PaymentStatus


class _DummySession:
    async def commit(self):
        return None

    async def rollback(self):
        return None


class _DummySessionFactory:
    def __call__(self):
        return self

    async def __aenter__(self):
        return _DummySession()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_payment_completed_sends_receipt_email(monkeypatch):
    notifications: list[dict] = []
    emails: list[dict] = []
    ride_id = uuid4()
    user_id = uuid4()
    transaction_id = uuid4()

    class DummyNotificationService:
        async def create_notification(self, **kwargs):
            notifications.append(kwargs)

    class DummyUserClient:
        async def get_user_settings(self, requested_user_id):
            assert requested_user_id == user_id
            return {"email_ride_receipts": True}

        async def get_user_email(self, requested_user_id):
            assert requested_user_id == user_id
            return {"email": "rider@example.com", "name": "Rider One"}

    class DummyPaymentClient:
        async def get_receipt(self, requested_ride_id, requested_user_id):
            assert requested_ride_id == ride_id
            assert requested_user_id == user_id
            return {
                "trip_number": "TRIP-ABC123",
                "currency": "CAD",
                "total_fare": 42.5,
                "ride_date": "2026-05-11T09:00:00Z",
                "pickup_address": "1 Main St",
                "destination_address": "2 Elm St",
                "payment_method_type": "visa",
                "payment_method_last_four": "4242",
                "paid_at": "2026-05-11T09:45:00Z",
            }

    async def dummy_send_payment_receipt_email(**kwargs):
        emails.append(kwargs)
        return True

    monkeypatch.setattr(consumers, "NotificationRepository", lambda session: object())
    monkeypatch.setattr(consumers, "NotificationService", lambda repo: DummyNotificationService())
    monkeypatch.setattr(consumers, "UserServiceClient", lambda base_url: DummyUserClient())
    monkeypatch.setattr(consumers, "PaymentServiceClient", lambda base_url: DummyPaymentClient())
    monkeypatch.setattr(consumers, "send_payment_receipt_email", dummy_send_payment_receipt_email)

    consumer = consumers.PaymentEventConsumer(object(), _DummySessionFactory())
    envelope = EventEnvelope(
        event_type=RoutingKeys.PAYMENT_COMPLETED,
        payload=PaymentCompletedPayload(
            transaction_id=transaction_id,
            ride_id=ride_id,
            user_id=user_id,
            amount=42.5,
            status=PaymentStatus.COMPLETED,
        ).model_dump(mode="json"),
    )

    await consumer.handle(envelope)

    assert len(notifications) == 1
    assert notifications[0]["title"] == "Payment Processed"
    assert notifications[0]["data"]["screen"] == "payment_receipt"
    assert len(emails) == 1
    assert emails[0]["to"] == "rider@example.com"
    assert emails[0]["name"] == "Rider One"
    assert emails[0]["receipt"]["trip_number"] == "TRIP-ABC123"


@pytest.mark.asyncio
async def test_payment_completed_skips_receipt_email_when_disabled(monkeypatch):
    emails: list[dict] = []
    user_id = uuid4()

    class DummyNotificationService:
        async def create_notification(self, **kwargs):
            return None

    class DummyUserClient:
        async def get_user_settings(self, requested_user_id):
            assert requested_user_id == user_id
            return {"email_ride_receipts": False}

        async def get_user_email(self, requested_user_id):
            raise AssertionError("email lookup should not happen when receipts are disabled")

    class DummyPaymentClient:
        async def get_receipt(self, requested_ride_id, requested_user_id):
            raise AssertionError("receipt lookup should not happen when receipts are disabled")

    async def dummy_send_payment_receipt_email(**kwargs):
        emails.append(kwargs)
        return True

    monkeypatch.setattr(consumers, "NotificationRepository", lambda session: object())
    monkeypatch.setattr(consumers, "NotificationService", lambda repo: DummyNotificationService())
    monkeypatch.setattr(consumers, "UserServiceClient", lambda base_url: DummyUserClient())
    monkeypatch.setattr(consumers, "PaymentServiceClient", lambda base_url: DummyPaymentClient())
    monkeypatch.setattr(consumers, "send_payment_receipt_email", dummy_send_payment_receipt_email)

    consumer = consumers.PaymentEventConsumer(object(), _DummySessionFactory())
    envelope = EventEnvelope(
        event_type=RoutingKeys.PAYMENT_COMPLETED,
        payload=PaymentCompletedPayload(
            transaction_id=uuid4(),
            ride_id=uuid4(),
            user_id=user_id,
            amount=19.99,
            status=PaymentStatus.COMPLETED,
        ).model_dump(mode="json"),
    )

    await consumer.handle(envelope)

    assert emails == []
