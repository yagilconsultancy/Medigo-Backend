import asyncio
import os

os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("ENVIRONMENT", "development")

import pytest

import app.services.contact_message_service as svc


class _Repo:
    def __init__(self, session):
        pass

    async def create(self, msg):
        msg.id = "msg-1"
        return msg


@pytest.fixture
def sent(monkeypatch):
    calls = []

    async def fake_send(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(svc, "ContactMessageRepository", _Repo)
    monkeypatch.setattr(svc, "send_email", fake_send)
    return calls


def _submit(**overrides):
    data = dict(
        full_name="Test Person",
        email="visitor@example.com",
        phone=None,
        service_type="General Support",
        message="Hello",
    )
    data.update(overrides)
    return asyncio.run(svc.ContactMessageService(session=None).submit_message(**data))


def test_contact_email_goes_to_admin_recipients_with_reply_to(sent, monkeypatch):
    monkeypatch.setattr(svc.settings, "ADMIN_BOOKING_ALERT_EMAILS", "admin@getmedigo.com")
    _submit()
    assert len(sent) == 1
    assert sent[0]["to"] == "admin@getmedigo.com"
    assert sent[0]["reply_to"] == "visitor@example.com"


def test_visitor_text_is_escaped(sent, monkeypatch):
    monkeypatch.setattr(svc.settings, "ADMIN_BOOKING_ALERT_EMAILS", "admin@getmedigo.com")
    _submit(full_name="<b>x</b>", message="<script>alert(1)</script>")
    body = sent[0]["html_body"]
    assert "<script>" not in body
    assert "&lt;script&gt;" in body


def test_email_failure_still_saves_message(monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(svc, "ContactMessageRepository", _Repo)
    monkeypatch.setattr(svc, "send_email", boom)
    msg = _submit()
    assert msg.id == "msg-1"
