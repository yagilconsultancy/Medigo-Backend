from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1 import admin_role_endpoints as ep


def _patch(monkeypatch, email, role_names, exempt=""):
    user_repo = MagicMock()
    user_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(email=email) if email is not None else None
    )
    role_repo = MagicMock()
    role_repo.get_user_roles = AsyncMock(
        return_value=[SimpleNamespace(name=n) for n in role_names]
    )
    monkeypatch.setattr(ep, "UserRepository", lambda session: user_repo)
    monkeypatch.setattr(ep, "AdminRoleRepository", lambda session: role_repo)
    monkeypatch.setattr(ep.settings, "ROLE_ADMIN_EXEMPT_EMAILS", exempt)


def _admin():
    return SimpleNamespace(id=uuid4())


@pytest.mark.asyncio
async def test_super_admin_is_allowed(monkeypatch):
    _patch(monkeypatch, "client@example.com", ["super_admin"])
    admin = _admin()
    assert await ep.require_role_manager(admin, MagicMock()) is admin


@pytest.mark.asyncio
async def test_other_admin_roles_are_refused(monkeypatch):
    _patch(monkeypatch, "support@example.com", ["support_admin"])
    with pytest.raises(HTTPException) as exc:
        await ep.require_role_manager(_admin(), MagicMock())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_with_no_role_is_refused(monkeypatch):
    _patch(monkeypatch, "nobody@example.com", [])
    with pytest.raises(HTTPException) as exc:
        await ep.require_role_manager(_admin(), MagicMock())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_exempt_email_is_allowed_without_a_role_case_insensitive(monkeypatch):
    _patch(monkeypatch, "Owner@Example.com", [], exempt=" other@x.com , owner@example.COM ")
    admin = _admin()
    assert await ep.require_role_manager(admin, MagicMock()) is admin


@pytest.mark.asyncio
async def test_empty_exempt_list_exempts_nobody(monkeypatch):
    _patch(monkeypatch, "owner@example.com", [], exempt="")
    with pytest.raises(HTTPException):
        await ep.require_role_manager(_admin(), MagicMock())


@pytest.mark.asyncio
async def test_missing_user_record_is_refused(monkeypatch):
    _patch(monkeypatch, None, [], exempt="owner@example.com")
    with pytest.raises(HTTPException):
        await ep.require_role_manager(_admin(), MagicMock())
