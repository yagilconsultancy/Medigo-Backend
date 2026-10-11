from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services.document_service import DocumentService
from app.services.fleet_scope import ensure_driver_in_scope
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import UserRole


def _repo(driver_business_id=None, exists=True):
    driver = SimpleNamespace(business_id=driver_business_id) if exists else None
    return SimpleNamespace(get_by_user_id=AsyncMock(return_value=driver))


@pytest.mark.asyncio
async def test_admin_may_act_on_any_driver():
    repo = _repo(uuid4())
    await ensure_driver_in_scope(repo, UserClaims(id=uuid4(), role=UserRole.ADMIN), uuid4())
    repo.get_by_user_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_business_may_act_on_own_fleet_driver():
    fleet = uuid4()
    actor = UserClaims(id=uuid4(), role=UserRole.BUSINESS, business_id=fleet)
    await ensure_driver_in_scope(_repo(fleet), actor, uuid4())


@pytest.mark.asyncio
async def test_business_cannot_act_on_another_fleets_driver():
    actor = UserClaims(id=uuid4(), role=UserRole.BUSINESS, business_id=uuid4())
    with pytest.raises(NotFoundError):
        await ensure_driver_in_scope(_repo(uuid4()), actor, uuid4())


@pytest.mark.asyncio
async def test_business_without_fleet_is_refused():
    actor = UserClaims(id=uuid4(), role=UserRole.BUSINESS)
    with pytest.raises(NotFoundError):
        await ensure_driver_in_scope(_repo(None), actor, uuid4())


@pytest.mark.asyncio
async def test_business_cannot_reach_a_non_driver_user():
    actor = UserClaims(id=uuid4(), role=UserRole.BUSINESS, business_id=uuid4())
    with pytest.raises(NotFoundError):
        await ensure_driver_in_scope(_repo(exists=False), actor, uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.RIDER, UserRole.DRIVER, UserRole.FACILITY])
async def test_other_roles_are_refused(role):
    actor = UserClaims(id=uuid4(), role=role, business_id=uuid4())
    with pytest.raises(NotFoundError):
        await ensure_driver_in_scope(_repo(actor.business_id), actor, uuid4())


@pytest.mark.asyncio
async def test_verify_document_rejects_a_document_of_another_user():
    owner = uuid4()
    doc = SimpleNamespace(id=uuid4(), user_id=owner)
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=doc), update_status=AsyncMock()
    )
    service = DocumentService.__new__(DocumentService)
    service.document_repo = repo

    with pytest.raises(NotFoundError):
        await service.verify_document(
            document_id=doc.id,
            admin_id=uuid4(),
            status="approved",
            expected_user_id=uuid4(),  # a different user than the owner
        )
    repo.update_status.assert_not_awaited()
