from unittest.mock import AsyncMock

import pytest

from app.realtime import socket_manager


@pytest.fixture
def fake_sio(monkeypatch):
    monkeypatch.setattr(
        socket_manager.sio, "get_session", AsyncMock(return_value={"user_id": "u1"})
    )
    monkeypatch.setattr(socket_manager.sio, "emit", AsyncMock())
    return socket_manager.sio


@pytest.mark.asyncio
async def test_typing_from_outside_the_conversation_is_ignored(monkeypatch, fake_sio):
    monkeypatch.setattr(fake_sio, "rooms", lambda sid, namespace=None: ["some-other-room"])
    await socket_manager.on_typing("sid1", {"conversation_id": "c1"})
    fake_sio.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_typing_from_a_member_is_broadcast(monkeypatch, fake_sio):
    monkeypatch.setattr(fake_sio, "rooms", lambda sid, namespace=None: ["chat_c1"])
    await socket_manager.on_typing("sid1", {"conversation_id": "c1"})
    fake_sio.emit.assert_awaited_once()
