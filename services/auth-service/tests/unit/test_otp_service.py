from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.services import otp_service as otp_module


@pytest.mark.asyncio
async def test_generate_otp_uses_dynamic_generator(monkeypatch):
    otp_repo = SimpleNamespace(
        count_recent_for_user=AsyncMock(return_value=0),
        create=AsyncMock(),
    )
    monkeypatch.setattr(otp_module, "generate_otp", lambda: "482913")

    service = otp_module.OTPService(otp_repo)
    code = await service.generate_otp(uuid4(), "registration", "email")

    assert code == "482913"
    created_otp = otp_repo.create.await_args.args[0]
    assert created_otp.code == "482913"
    assert created_otp.code != "123456"
