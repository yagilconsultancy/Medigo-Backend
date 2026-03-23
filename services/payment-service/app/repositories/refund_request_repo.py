from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refund_request import RefundRequest


_STATUS_MAP = {
    "pending": ["pending"],
    "approved": ["approved"],
    "rejected": ["rejected"],
}


class RefundRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, refund: RefundRequest) -> RefundRequest:
        self.session.add(refund)
        await self.session.flush()
        await self.session.refresh(refund)
        return refund

    async def get_by_id(self, refund_id: UUID) -> RefundRequest | None:
        result = await self.session.execute(
            select(RefundRequest).where(RefundRequest.id == refund_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ride_id(self, ride_id: UUID) -> RefundRequest | None:
        result = await self.session.execute(
            select(RefundRequest).where(RefundRequest.ride_id == ride_id)
        )
        return result.scalar_one_or_none()

    async def get_kpis(self) -> dict:
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(RefundRequest.status == "pending").label("pending"),
                func.count().filter(RefundRequest.status == "approved").label("approved"),
                func.count().filter(RefundRequest.status == "rejected").label("rejected"),
            )
        )
        row = result.one()
        return {
            "total_requests": row.total,
            "pending_review": row.pending,
            "approved": row.approved,
            "rejected": row.rejected,
        }

    async def get_all(
        self,
        status_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[RefundRequest], int]:
        conditions = []

        if status_filter and status_filter in _STATUS_MAP:
            conditions.append(RefundRequest.status.in_(_STATUS_MAP[status_filter]))

        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    RefundRequest.id.cast(str).ilike(pattern),
                    RefundRequest.ride_id.cast(str).ilike(pattern),
                    RefundRequest.category.ilike(pattern),
                )
            )

        base_query = select(RefundRequest)
        if conditions:
            base_query = base_query.where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(RefundRequest.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, refund_id: UUID, **kwargs) -> None:
        refund = await self.get_by_id(refund_id)
        if refund:
            for key, value in kwargs.items():
                setattr(refund, key, value)
            await self.session.flush()
