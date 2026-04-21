from uuid import uuid4
import sys
import types

import pytest

stripe_stub = types.ModuleType("stripe")
stripe_stub.error = types.SimpleNamespace(StripeError=Exception, CardError=Exception)
sys.modules.setdefault("stripe", stripe_stub)

from app.services.payment_method_service import PaymentMethodService
from mediride_common.exceptions import ValidationError


@pytest.mark.asyncio
async def test_add_payment_method_rejects_missing_stripe_source_before_repo_access():
    service = PaymentMethodService(pm_repo=None, stripe_client=None)

    with pytest.raises(ValidationError, match="Raw card data is not accepted"):
        await service.add_payment_method(
            user_id=uuid4(),
            method_type="card",
            holder_name="Test Card",
        )
