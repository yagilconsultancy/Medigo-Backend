import os
import sys
import types

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

import app.dependencies as dependencies
from app.events import consumers
from mediride_common.events.constants import RoutingKeys


@pytest.mark.asyncio
async def test_setup_consumers_binds_admin_invite_events(monkeypatch):
    calls: list[dict] = []

    class DummyAuthConsumer:
        def __init__(self, broker):
            self.broker = broker

        async def setup_queue(self, **kwargs):
            calls.append({"consumer": "auth", **kwargs})

    class DummyRideConsumer:
        def __init__(self, broker, session_factory):
            self.broker = broker
            self.session_factory = session_factory

        async def setup_queue(self, **kwargs):
            calls.append({"consumer": "ride", **kwargs})

    class DummyPaymentConsumer:
        def __init__(self, broker, session_factory):
            self.broker = broker
            self.session_factory = session_factory

        async def setup_queue(self, **kwargs):
            calls.append({"consumer": "payment", **kwargs})

    class DummyChatConsumer:
        def __init__(self, broker, session_factory):
            self.broker = broker
            self.session_factory = session_factory

        async def setup_queue(self, **kwargs):
            calls.append({"consumer": "chat", **kwargs})

    monkeypatch.setattr(dependencies, "get_session_factory", lambda: object())
    monkeypatch.setattr(consumers, "AuthEventConsumer", DummyAuthConsumer)
    monkeypatch.setattr(consumers, "RideEventConsumer", DummyRideConsumer)
    monkeypatch.setattr(consumers, "PaymentEventConsumer", DummyPaymentConsumer)
    monkeypatch.setattr(consumers, "ChatConversationConsumer", DummyChatConsumer)

    await consumers.setup_consumers(broker=object())

    auth_call = next(call for call in calls if call["consumer"] == "auth")
    assert RoutingKeys.ADMIN_INVITE_SENT in auth_call["routing_keys"]
    assert RoutingKeys.USER_OTP_REQUESTED in auth_call["routing_keys"]
