import logging
from uuid import UUID

from app.models.driver_profile import DriverProfile
from app.repositories.driver_repo import DriverRepository
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import DriverApprovedPayload, DriverStatusPayload
from mediride_common.exceptions import NotFoundError
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class DriverService:
    def __init__(
        self,
        driver_repo: DriverRepository,
        publisher: EventPublisher,
    ):
        self.driver_repo = driver_repo
        self.publisher = publisher

    async def create_driver_profile(
        self,
        user_id: UUID,
        business_id: UUID,
        invited_via_email: str | None = None,
    ) -> DriverProfile:
        driver = DriverProfile(
            user_id=user_id,
            business_id=business_id,
            invited_via_email=invited_via_email,
        )
        await self.driver_repo.create(driver)
        logger.info(f"Driver profile created: {user_id}")
        return driver

    async def get_driver_profile(self, user_id: UUID) -> DriverProfile:
        driver = await self.driver_repo.get_by_user_id(user_id)
        if not driver:
            raise NotFoundError("Driver profile not found")
        return driver

    async def update_driver_profile(self, user_id: UUID, **kwargs) -> DriverProfile:
        driver = await self.driver_repo.get_by_user_id(user_id)
        if not driver:
            raise NotFoundError("Driver profile not found")
        await self.driver_repo.update(user_id, **kwargs)
        return await self.driver_repo.get_by_user_id(user_id)

    async def approve_driver(self, driver_user_id: UUID) -> DriverProfile:
        driver = await self.driver_repo.get_by_user_id(driver_user_id)
        if not driver:
            raise NotFoundError("Driver profile not found")

        await self.driver_repo.update(
            driver_user_id,
            is_approved=True,
            background_check_status="approved",
            approved_at=utc_now(),
        )

        await self.publisher.publish(
            Exchanges.USERS,
            RoutingKeys.DRIVER_APPROVED,
            DriverApprovedPayload(
                driver_id=driver_user_id,
                business_id=driver.business_id,
            ).model_dump(mode="json"),
        )

        logger.info(f"Driver approved: {driver_user_id}")
        return await self.driver_repo.get_by_user_id(driver_user_id)

    async def suspend_driver(self, driver_user_id: UUID) -> DriverProfile:
        driver = await self.driver_repo.get_by_user_id(driver_user_id)
        if not driver:
            raise NotFoundError("Driver profile not found")

        await self.driver_repo.update(
            driver_user_id,
            is_approved=False,
            is_online=False,
        )
        return await self.driver_repo.get_by_user_id(driver_user_id)

    async def set_online_status(
        self, user_id: UUID, is_online: bool
    ) -> DriverProfile:
        driver = await self.driver_repo.get_by_user_id(user_id)
        if not driver:
            raise NotFoundError("Driver profile not found")

        if not driver.is_approved and is_online:
            raise NotFoundError("Driver must be approved to go online")

        await self.driver_repo.set_online_status(user_id, is_online)

        routing_key = RoutingKeys.DRIVER_ONLINE if is_online else RoutingKeys.DRIVER_OFFLINE
        await self.publisher.publish(
            Exchanges.USERS,
            routing_key,
            DriverStatusPayload(
                driver_id=user_id,
                is_online=is_online,
                business_id=driver.business_id,
            ).model_dump(mode="json"),
        )

        return await self.driver_repo.get_by_user_id(user_id)

    async def list_drivers(
        self,
        business_id: UUID,
        offset: int = 0,
        limit: int = 20,
        is_online: bool | None = None,
        is_approved: bool | None = None,
    ) -> tuple[list[DriverProfile], int]:
        return await self.driver_repo.list_by_business(
            business_id, offset, limit, is_online, is_approved
        )
