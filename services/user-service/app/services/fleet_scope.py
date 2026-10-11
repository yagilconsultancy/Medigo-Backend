"""Fleet scoping for BUSINESS callers.

A BUSINESS user may only act on drivers that belong to their own fleet.
ADMIN may act on any driver. Anyone else, or a fleet user whose account has no
fleet attached, is treated as if the driver did not exist (404), so driver ids
cannot be probed.
"""

from uuid import UUID

from app.repositories.driver_repo import DriverRepository
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.enums import UserRole


async def ensure_driver_in_scope(
    driver_repo: DriverRepository, actor: UserClaims, driver_user_id: UUID
) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if actor.role == UserRole.BUSINESS and actor.business_id:
        driver = await driver_repo.get_by_user_id(driver_user_id)
        if driver and driver.business_id == actor.business_id:
            return
    raise NotFoundError("Driver not found")
