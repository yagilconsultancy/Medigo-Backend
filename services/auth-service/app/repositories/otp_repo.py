from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.otp import OTPRecord
from mediride_common.utils import utc_now


class OTPRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, otp: OTPRecord) -> OTPRecord:
        self.session.add(otp)
        await self.session.flush()
        return otp

    async def get_latest_unverified(
        self, user_id: UUID, purpose: str
    ) -> OTPRecord | None:
        result = await self.session.execute(
            select(OTPRecord)
            .where(
                OTPRecord.user_id == user_id,
                OTPRecord.purpose == purpose,
                OTPRecord.verified_at.is_(None),
                OTPRecord.expires_at > utc_now(),
            )
            .order_by(OTPRecord.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_verified(self, otp_id: UUID) -> None:
        await self.session.execute(
            update(OTPRecord)
            .where(OTPRecord.id == otp_id)
            .values(verified_at=utc_now())
        )

    async def increment_attempts(self, otp_id: UUID) -> None:
        otp = await self.session.get(OTPRecord, otp_id)
        if otp:
            otp.attempts += 1
            await self.session.flush()

    async def count_recent_for_user(self, user_id: UUID, hours: int = 1) -> int:
        from datetime import timedelta

        cutoff = utc_now() - timedelta(hours=hours)
        result = await self.session.execute(
            select(func.count())
            .select_from(OTPRecord)
            .where(
                OTPRecord.user_id == user_id,
                OTPRecord.created_at > cutoff,
            )
        )
        return result.scalar_one()
