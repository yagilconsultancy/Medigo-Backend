from sqlalchemy import Boolean, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.login_record import LoginRecord


class LoginRecordRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, record: LoginRecord) -> LoginRecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def list_records(
        self,
        success: bool | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[LoginRecord], int]:
        query = select(LoginRecord)
        count_query = select(func.count(LoginRecord.id))

        if success is not None:
            query = query.where(LoginRecord.success == success)
            count_query = count_query.where(LoginRecord.success == success)

        if search:
            search_filter = or_(
                LoginRecord.admin_name.ilike(f"%{search}%"),
                LoginRecord.admin_email.ilike(f"%{search}%"),
                LoginRecord.ip_address.ilike(f"%{search}%"),
                LoginRecord.location.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total = (await self.session.execute(count_query)).scalar() or 0
        rows = (
            await self.session.execute(
                query.order_by(LoginRecord.created_at.desc()).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def get_kpi_counts(self) -> dict:
        total = (await self.session.execute(select(func.count(LoginRecord.id)))).scalar() or 0
        successful = (
            await self.session.execute(
                select(func.count(LoginRecord.id)).where(LoginRecord.success.is_(True))
            )
        ).scalar() or 0
        failed = (
            await self.session.execute(
                select(func.count(LoginRecord.id)).where(LoginRecord.success.is_(False))
            )
        ).scalar() or 0
        unique_locations = (
            await self.session.execute(
                select(func.count(func.distinct(LoginRecord.location))).where(LoginRecord.location.isnot(None))
            )
        ).scalar() or 0

        return {
            "total_logins": total,
            "successful": successful,
            "failed_attempts": failed,
            "unique_locations": unique_locations,
        }

    async def get_suspicious_count(self) -> int:
        result = await self.session.execute(
            select(func.count(LoginRecord.id)).where(LoginRecord.is_suspicious.is_(True))
        )
        return result.scalar() or 0
