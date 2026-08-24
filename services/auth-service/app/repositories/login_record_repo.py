from datetime import datetime, timedelta

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
        # `location` is never populated (no GeoIP lookup exists), so counting
        # distinct locations is structurally always 0. Count distinct IPs
        # instead so the KPI reflects something real.
        unique_locations = (
            await self.session.execute(
                select(func.count(func.distinct(LoginRecord.ip_address))).where(
                    LoginRecord.ip_address.isnot(None)
                )
            )
        ).scalar() or 0

        suspicious = await self.get_suspicious_count()

        return {
            "total_logins": total,
            "successful": successful,
            "failed_attempts": failed,
            "unique_locations": unique_locations,
            "suspicious_count": suspicious,
        }

    async def count_recent_failures(self, admin_email: str, since: datetime) -> int:
        """Failed attempts for an email since a cutoff, used to flag suspicion."""
        result = await self.session.execute(
            select(func.count(LoginRecord.id)).where(
                LoginRecord.admin_email == admin_email,
                LoginRecord.success.is_(False),
                LoginRecord.created_at >= since,
            )
        )
        return result.scalar() or 0

    async def has_successful_login_from_ip(
        self, admin_email: str, ip_address: str
    ) -> bool:
        """True if this email has ever logged in successfully from this IP."""
        result = await self.session.execute(
            select(LoginRecord.id)
            .where(
                LoginRecord.admin_email == admin_email,
                LoginRecord.ip_address == ip_address,
                LoginRecord.success.is_(True),
            )
            .limit(1)
        )
        return result.scalar() is not None

    async def get_suspicious_count(self) -> int:
        result = await self.session.execute(
            select(func.count(LoginRecord.id)).where(LoginRecord.is_suspicious.is_(True))
        )
        return result.scalar() or 0

    async def count_blocked_recent(self, days: int = 30) -> int:
        """Failed sign-in attempts in the window, for the "threats blocked" KPI.

        Only meaningful once failed attempts are actually persisted -- they
        used to be rolled back with the request transaction.
        """
        from mediride_common.utils import utc_now

        since = utc_now() - timedelta(days=days)
        result = await self.session.execute(
            select(func.count(LoginRecord.id)).where(
                LoginRecord.success.is_(False),
                LoginRecord.created_at >= since,
            )
        )
        return result.scalar() or 0
