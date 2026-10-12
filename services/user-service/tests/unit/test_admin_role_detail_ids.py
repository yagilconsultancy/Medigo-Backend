from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.admin_role_service import AdminRoleService


@pytest.mark.asyncio
async def test_role_detail_admins_include_id_for_back_office_remove_button():
    user_id = uuid4()
    assigned = datetime(2026, 6, 12, tzinfo=timezone.utc)
    role = SimpleNamespace(
        id=uuid4(),
        name="support_admin",
        display_name="Support Admin",
        description="",
        color="#000000",
        is_system=True,
        created_at=assigned,
        assignments=[SimpleNamespace(user_id=user_id, assigned_at=assigned)],
    )
    role_repo = MagicMock()
    role_repo.get_by_id = AsyncMock(return_value=role)
    user_repo = MagicMock()
    user_repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(id=user_id, first_name="A", last_name="B", email="a@b.c")
    )

    service = AdminRoleService(role_repo, user_repo)
    detail = await service.get_role_detail(role.id)

    admin = detail.admins[0]
    assert admin["id"] == str(user_id)
    assert admin["user_id"] == str(user_id)
    assert admin["created_at"].startswith("2026-06-12")
