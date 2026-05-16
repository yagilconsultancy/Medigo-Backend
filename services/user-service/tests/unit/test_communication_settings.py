from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.settings_endpoints import (
    _to_communication_response,
    update_communication_settings,
)
from app.schemas.settings import UpdateCommunicationSettings


class _FakeRepo:
    def __init__(self, settings):
        self.settings = settings
        self.updated = None

    async def get_or_create(self, user_id):
        return self.settings

    async def update(self, user_id, **kwargs):
        self.updated = kwargs
        for key, value in kwargs.items():
            setattr(self.settings, key, value)

    async def get_by_user_id(self, user_id):
        return self.settings


def test_to_communication_response_collapses_existing_settings():
    settings = SimpleNamespace(
        sms_ride_updates=True,
        push_ride_updates=False,
        push_chat_messages=True,
        email_weekly_summary=False,
    )

    response = _to_communication_response(settings)

    assert response.sms_alerts is True
    assert response.push_notifications is True
    assert response.promotional_emails is False


@pytest.mark.asyncio
async def test_update_communication_settings_maps_screen_toggles_to_settings_fields():
    settings = SimpleNamespace(
        sms_ride_updates=False,
        push_ride_updates=False,
        push_chat_messages=False,
        email_weekly_summary=False,
    )
    repo = _FakeRepo(settings)
    user = SimpleNamespace(id=uuid4())

    response = await update_communication_settings(
        body=UpdateCommunicationSettings(
            sms_alerts=True,
            push_notifications=True,
            promotional_emails=True,
        ),
        user=user,
        repo=repo,
    )

    assert repo.updated == {
        "sms_ride_updates": True,
        "push_ride_updates": True,
        "push_chat_messages": True,
        "email_weekly_summary": True,
    }
    assert response.data.sms_alerts is True
    assert response.data.push_notifications is True
    assert response.data.promotional_emails is True
    assert response.message == "Communication settings updated"
