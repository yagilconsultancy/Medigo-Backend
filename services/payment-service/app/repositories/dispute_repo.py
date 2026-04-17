from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispute import Dispute, DisputeNote


_STATUS_MAP = {
    "under_review": ["under_review"],
    "approved": ["approved"],
    "rejected": ["rejected"],
}


class DisputeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dispute: Dispute) -> Dispute:
        # Generate dispute number from sequence
        result = await self.session.execute(text("SELECT nextval('dispute_seq')"))
        dispute.dispute_number = result.scalar_one()

        self.session.add(dispute)
        await self.session.flush()
        await self.session.refresh(dispute)
        return dispute

    async def get_by_id(self, dispute_id: UUID) -> Dispute | None:
        result = await self.session.execute(
            select(Dispute).where(Dispute.id == dispute_id)
        )
        return result.scalar_one_or_none()

    async def get_kpis(self) -> dict:
        result = await self.session.execute(
            select(
                func.count().filter(Dispute.status == "under_review").label("open_disputes"),
                func.count().filter(Dispute.status == "approved").label("approved"),
                func.count().filter(Dispute.status == "rejected").label("rejected"),
            )
        )
        row = result.one()
        return {
            "open_disputes": row.open_disputes,
            "refunds_approved": row.approved,
            "rejected": row.rejected,
        }

    async def get_all(
        self,
        status_filter: str | None = None,
        dispute_type_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Dispute], int]:
        conditions = []

        if status_filter and status_filter in _STATUS_MAP:
            conditions.append(Dispute.status.in_(_STATUS_MAP[status_filter]))

        if dispute_type_filter:
            conditions.append(Dispute.dispute_type == dispute_type_filter)

        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Dispute.dispute_number.cast(str).ilike(pattern),
                    Dispute.trip_code.ilike(pattern),
                    Dispute.rider_name.ilike(pattern),
                    Dispute.driver_name.ilike(pattern),
                )
            )

        base_query = select(Dispute)
        if conditions:
            base_query = base_query.where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(Dispute.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, dispute_id: UUID, **kwargs) -> None:
        dispute = await self.get_by_id(dispute_id)
        if dispute:
            for key, value in kwargs.items():
                setattr(dispute, key, value)
            await self.session.flush()


class DisputeNoteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, note: DisputeNote) -> DisputeNote:
        self.session.add(note)
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def get_by_dispute_id(self, dispute_id: UUID) -> list[DisputeNote]:
        result = await self.session.execute(
            select(DisputeNote)
            .where(DisputeNote.dispute_id == dispute_id)
            .order_by(DisputeNote.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, note_id: UUID) -> DisputeNote | None:
        result = await self.session.execute(
            select(DisputeNote).where(DisputeNote.id == note_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, note_id: UUID) -> bool:
        note = await self.get_by_id(note_id)
        if note:
            await self.session.delete(note)
            await self.session.flush()
            return True
        return False
