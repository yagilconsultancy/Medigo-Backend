import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rider_issue import RiderIssue
from app.models.rider_issue_note import RiderIssueNote
from app.models.user import User


class RiderIssueRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, issue: RiderIssue) -> RiderIssue:
        self.session.add(issue)
        await self.session.flush()
        await self.session.refresh(issue)
        return issue

    async def get_by_id(self, issue_id: UUID) -> RiderIssue | None:
        result = await self.session.execute(
            select(RiderIssue).where(RiderIssue.id == issue_id)
        )
        return result.scalar_one_or_none()

    async def list_issues(
        self,
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        query = (
            select(RiderIssue, User.first_name, User.last_name)
            .join(User, User.id == RiderIssue.rider_id)
        )

        if status:
            query = query.where(RiderIssue.status == status)
        if priority:
            query = query.where(RiderIssue.priority == priority)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    RiderIssue.subject.ilike(pattern),
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                )
            )

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(RiderIssue.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        rows = result.all()

        issues = []
        for issue, first_name, last_name in rows:
            issues.append({
                "id": issue.id,
                "ticket_number": f"TKT-{issue.ticket_number}",
                "rider_id": issue.rider_id,
                "rider_name": f"{first_name} {last_name}",
                "issue_type": issue.issue_type,
                "subject": issue.subject,
                "status": issue.status,
                "priority": issue.priority,
                "created_at": issue.created_at,
            })

        return issues, total

    async def get_issue_kpis(self) -> dict:
        result = await self.session.execute(
            select(RiderIssue.status, func.count())
            .group_by(RiderIssue.status)
        )
        counts = {row[0]: row[1] for row in result.all()}

        return {
            "open_count": counts.get("open", 0),
            "under_review_count": counts.get("under_review", 0),
            "resolved_count": counts.get("resolved", 0),
        }

    async def add_note(self, note: RiderIssueNote) -> RiderIssueNote:
        self.session.add(note)
        await self.session.flush()
        await self.session.refresh(note)
        return note

    async def update_status(
        self, issue_id: UUID, new_status: str, resolved_at: datetime | None = None
    ) -> None:
        values: dict = {"status": new_status}
        if resolved_at:
            values["resolved_at"] = resolved_at
        await self.session.execute(
            update(RiderIssue).where(RiderIssue.id == issue_id).values(**values)
        )

    async def count_open_for_rider(self, rider_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(
                RiderIssue.rider_id == rider_id,
                RiderIssue.status.in_(["open", "under_review"]),
            )
        )
        return result.scalar_one()

    async def count_open_batch(self, rider_ids: list[UUID]) -> dict[UUID, int]:
        if not rider_ids:
            return {}
        result = await self.session.execute(
            select(RiderIssue.rider_id, func.count())
            .where(
                RiderIssue.rider_id.in_(rider_ids),
                RiderIssue.status.in_(["open", "under_review"]),
            )
            .group_by(RiderIssue.rider_id)
        )
        return {row[0]: row[1] for row in result.all()}
