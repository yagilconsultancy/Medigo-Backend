from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride_request import RideRequest
from mediride_common.schemas.enums import RideRequestStatus
from mediride_common.utils import utc_now


class RideRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, request: RideRequest) -> RideRequest:
        self.session.add(request)
        await self.session.flush()
        return request

    async def get_by_id(self, request_id: UUID) -> RideRequest | None:
        result = await self.session.execute(
            select(RideRequest).where(RideRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_for_driver(self, driver_id: UUID) -> list[RideRequest]:
        result = await self.session.execute(
            select(RideRequest).where(
                RideRequest.driver_id == driver_id,
                RideRequest.status == RideRequestStatus.PENDING,
                RideRequest.expires_at > utc_now(),
            ).order_by(RideRequest.sent_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_ride_id(self, ride_id: UUID) -> list[RideRequest]:
        result = await self.session.execute(
            select(RideRequest).where(
                RideRequest.ride_id == ride_id,
            ).order_by(RideRequest.sent_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, request_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(RideRequest).where(RideRequest.id == request_id).values(**kwargs)
        )

    async def expire_old_requests(self) -> int:
        now = utc_now()
        result = await self.session.execute(
            update(RideRequest)
            .where(
                RideRequest.status == RideRequestStatus.PENDING,
                RideRequest.expires_at <= now,
            )
            .values(status=RideRequestStatus.EXPIRED)
        )
        return result.rowcount
