from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.caregiver_profile import CaregiverProfile


class CaregiverRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, caregiver: CaregiverProfile) -> CaregiverProfile:
        self.session.add(caregiver)
        await self.session.flush()
        await self.session.refresh(caregiver)
        return caregiver

    async def get_by_user_id(self, user_id: UUID) -> CaregiverProfile | None:
        result = await self.session.execute(
            select(CaregiverProfile)
            .where(CaregiverProfile.user_id == user_id)
            .options(
                selectinload(CaregiverProfile.user),
                selectinload(CaregiverProfile.fleet),
            )
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        specialty: str | None = None,
        account_status: str | None = None,
        business_id: UUID | None = None,
    ) -> list[CaregiverProfile]:
        """Get all caregivers with optional filters."""
        query = select(CaregiverProfile).options(
            selectinload(CaregiverProfile.user),
            selectinload(CaregiverProfile.fleet),
        )

        if specialty:
            query = query.where(CaregiverProfile.specialty == specialty)
        if account_status:
            query = query.where(CaregiverProfile.account_status == account_status)
        if business_id:
            query = query.where(CaregiverProfile.business_id == business_id)

        query = query.order_by(CaregiverProfile.created_at.desc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_fleet(
        self,
        fleet_id: UUID,
        offset: int = 0,
        limit: int = 20,
        specialty: str | None = None,
        account_status: str | None = None,
    ) -> tuple[list[CaregiverProfile], int]:
        """Get caregivers for a specific fleet with pagination."""
        query = select(CaregiverProfile).where(CaregiverProfile.business_id == fleet_id)

        if specialty:
            query = query.where(CaregiverProfile.specialty == specialty)
        if account_status:
            query = query.where(CaregiverProfile.account_status == account_status)

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            query.options(
                selectinload(CaregiverProfile.user),
                selectinload(CaregiverProfile.fleet),
            )
            .offset(offset)
            .limit(limit)
            .order_by(CaregiverProfile.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, caregiver: CaregiverProfile) -> CaregiverProfile:
        """Update a caregiver profile instance."""
        await self.session.flush()
        await self.session.refresh(caregiver)
        return caregiver

    async def update_by_id(self, user_id: UUID, **kwargs) -> None:
        """Update caregiver by user_id with kwargs."""
        await self.session.execute(
            update(CaregiverProfile)
            .where(CaregiverProfile.user_id == user_id)
            .values(**kwargs)
        )

    async def set_online_status(self, user_id: UUID, is_online: bool) -> None:
        """Set caregiver online/offline status."""
        await self.update_by_id(user_id, is_online=is_online)

    async def suspend(
        self, user_id: UUID, reason: str, suspended_by: UUID
    ) -> None:
        """Suspend a caregiver."""
        from datetime import datetime
        await self.update_by_id(
            user_id,
            account_status="suspended",
            suspension_reason=reason,
            suspended_at=datetime.now(),
            suspended_by=suspended_by,
        )

    async def reactivate(self, user_id: UUID) -> None:
        """Reactivate a suspended caregiver."""
        await self.update_by_id(
            user_id,
            account_status="active",
            suspension_reason=None,
            suspended_at=None,
            suspended_by=None,
        )

    async def deactivate(self, user_id: UUID) -> None:
        """Deactivate a caregiver."""
        from datetime import datetime
        await self.update_by_id(
            user_id,
            account_status="deactivated",
            deactivated_at=datetime.now(),
        )
