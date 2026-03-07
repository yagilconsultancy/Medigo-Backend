from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.safety_report import SafetyReport


class SafetyReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, report: SafetyReport) -> SafetyReport:
        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)
        return report

    async def get_by_id(self, report_id: UUID) -> SafetyReport | None:
        result = await self.session.execute(
            select(SafetyReport).where(SafetyReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: UUID, offset: int = 0, limit: int = 20) -> tuple[list[SafetyReport], int]:
        query = (
            select(SafetyReport)
            .where(SafetyReport.reporter_id == user_id)
            .order_by(SafetyReport.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        reports = list(result.scalars().all())

        count_result = await self.session.execute(
            select(func.count(SafetyReport.id)).where(SafetyReport.reporter_id == user_id)
        )
        total = count_result.scalar() or 0

        return reports, total
