"""The admin invitation email links straight to the back office login."""
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services import email_service


@pytest.mark.asyncio
async def test_invite_email_contains_login_link(monkeypatch):
    monkeypatch.setattr(settings, "BACKOFFICE_URL", "https://backoffice.example.com/")
    sent = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", sent)

    assert await email_service.send_admin_invite_email(
        to="new.admin@example.com",
        full_name="New Admin",
        role_display_name="Support Admin",
        temporary_password="Tmp-Pass-123!",
        invited_by_name="Owner",
    )

    to, subject, html = sent.await_args.args
    assert to == "new.admin@example.com"
    assert html.count("https://backoffice.example.com/login") >= 2
    assert "//login" not in html.replace("https://", "")
    assert "one-time password" in html


@pytest.mark.asyncio
async def test_invite_email_fallback_also_has_link(monkeypatch):
    monkeypatch.setattr(settings, "BACKOFFICE_URL", "https://backoffice.example.com")
    sent = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_email", sent)
    monkeypatch.setattr(
        email_service._template_env,
        "get_template",
        lambda name: (_ for _ in ()).throw(RuntimeError("no template")),
    )

    await email_service.send_admin_invite_email(
        to="a@example.com",
        full_name="A",
        role_display_name="R",
        temporary_password="x",
        invited_by_name="O",
    )
    html = sent.await_args.args[2]
    assert "https://backoffice.example.com/login" in html
