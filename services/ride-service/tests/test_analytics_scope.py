from uuid import uuid4

import pytest

from app.api.v1.analytics_endpoints import _resolve_fleet_id
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import AuthorizationError
from mediride_common.schemas.enums import UserRole


def test_admin_sees_everything():
    user = UserClaims(id=uuid4(), role=UserRole.ADMIN)
    assert _resolve_fleet_id(user) is None


def test_business_with_fleet_is_scoped_to_it():
    fleet = uuid4()
    user = UserClaims(id=uuid4(), role=UserRole.BUSINESS, business_id=fleet)
    assert _resolve_fleet_id(user) == fleet


def test_business_without_fleet_is_refused_not_unfiltered():
    user = UserClaims(id=uuid4(), role=UserRole.BUSINESS)
    with pytest.raises(AuthorizationError):
        _resolve_fleet_id(user)
