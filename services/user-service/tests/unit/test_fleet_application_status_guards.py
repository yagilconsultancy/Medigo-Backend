from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.fleet_application_service import FleetApplicationService
from mediride_common.exceptions import ConflictError, NotFoundError
from mediride_common.schemas.enums import FleetApplicationStatus


def _service(application):
    app_repo = MagicMock()
    app_repo.get_by_id = AsyncMock(return_value=application)
    app_repo.update = AsyncMock()
    return FleetApplicationService(
        app_repo=app_repo,
        doc_repo=MagicMock(),
        fleet_repo=MagicMock(),
        publisher=MagicMock(),
    )


@pytest.mark.asyncio
async def test_approve_rejected_application_raises_conflict_not_500():
    """Approving an already-rejected application is a client error (409), not a 500."""
    application = SimpleNamespace(
        id=uuid4(), status=FleetApplicationStatus.REJECTED
    )
    service = _service(application)

    with pytest.raises(ConflictError) as exc:
        await service.approve_application(app_id=application.id, admin_id=uuid4())

    assert exc.value.status_code == 409
    assert "rejected" in exc.value.message


@pytest.mark.asyncio
async def test_reject_already_approved_application_raises_conflict():
    application = SimpleNamespace(
        id=uuid4(), status=FleetApplicationStatus.APPROVED
    )
    service = _service(application)

    with pytest.raises(ConflictError) as exc:
        await service.reject_application(
            app_id=application.id, admin_id=uuid4(), reason="dup"
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_request_info_on_approved_application_raises_conflict():
    application = SimpleNamespace(
        id=uuid4(), status=FleetApplicationStatus.APPROVED
    )
    service = _service(application)

    with pytest.raises(ConflictError) as exc:
        await service.request_info(
            app_id=application.id, admin_id=uuid4(), message="more docs"
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_missing_application_raises_not_found():
    service = _service(None)

    with pytest.raises(NotFoundError) as exc:
        await service.approve_application(app_id=uuid4(), admin_id=uuid4())

    assert exc.value.status_code == 404
