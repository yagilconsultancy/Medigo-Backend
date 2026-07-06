from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.auth_service import AuthService
from mediride_common.schemas.enums import UserRole


@pytest.mark.asyncio
async def test_register_driver_updates_password_for_precreated_admin_driver(monkeypatch):
    invite_token = "invite-token"
    new_password = "NewPassword1"
    business_id = uuid4()
    existing = MagicMock()
    existing.id = uuid4()
    existing.email = "driver@example.com"
    existing.role = UserRole.DRIVER
    existing.business_id = business_id
    existing.is_verified = False
    existing.password_hash = "old-hash"

    credential_repo = MagicMock()
    credential_repo.get_by_email_or_phone = AsyncMock(return_value=existing)
    credential_repo.update_password = AsyncMock()
    credential_repo.update_verified = AsyncMock()

    token_repo = MagicMock()
    token_repo.create = AsyncMock()

    otp_service = MagicMock()

    token_pair = MagicMock()
    token_pair.refresh_token = "refresh-token"

    jwt_handler = MagicMock()
    jwt_handler.create_token_pair = MagicMock(return_value=token_pair)

    publisher = MagicMock()

    user_service_client = MagicMock()
    user_service_client.verify_invite_token = AsyncMock(
        return_value={"email": existing.email, "business_id": str(business_id)}
    )
    user_service_client.accept_invitation = AsyncMock()

    auth_service = AuthService(
        credential_repo=credential_repo,
        token_repo=token_repo,
        otp_service=otp_service,
        jwt_handler=jwt_handler,
        publisher=publisher,
        user_service_client=user_service_client,
    )

    monkeypatch.setattr(
        "app.services.auth_service.hash_password",
        lambda password: f"hashed-{password}",
    )

    result = await auth_service.register_driver(invite_token, new_password)

    assert result is token_pair
    credential_repo.update_password.assert_awaited_once_with(
        existing.id, "hashed-NewPassword1"
    )
    user_service_client.accept_invitation.assert_awaited_once_with(
        invite_token, str(existing.id)
    )
    credential_repo.update_verified.assert_awaited_once_with(existing.id, True)
    jwt_handler.create_token_pair.assert_called_once_with(
        user_id=str(existing.id),
        role=existing.role,
        business_id=str(existing.business_id),
        email=existing.email,
    )
    token_repo.create.assert_awaited_once()
