from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog
from app.repositories.activity_log_repo import ActivityLogRepository


class ActivityLogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ActivityLogRepository(session)

    async def get_kpis(self) -> dict:
        severity_counts = await self.repo.get_severity_counts()
        total = sum(severity_counts.values())
        return {
            "total_logs": total,
            "info": severity_counts.get("info", 0),
            "warnings": severity_counts.get("warning", 0),
            "critical": severity_counts.get("critical", 0),
        }

    async def list_logs(
        self,
        severity: str | None = None,
        category: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        offset = (page - 1) * page_size
        logs, total = await self.repo.list_logs(
            severity=severity, category=category, search=search, offset=offset, limit=page_size
        )
        items = []
        for log in logs:
            items.append({
                "id": log.id,
                "action_title": log.action_title,
                "action_description": log.action_description,
                "category": log.category,
                "severity": log.severity,
                "admin_name": log.admin_name,
                "created_at": log.created_at,
            })
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def create_log(
        self,
        admin_id: UUID,
        admin_name: str,
        admin_email: str,
        action_title: str,
        action_description: str,
        category: str,
        severity: str = "info",
        target_entity_id: str | None = None,
        target_entity_type: str | None = None,
        ip_address: str | None = None,
    ) -> ActivityLog:
        log_number = await self.repo.get_next_log_number()
        log = ActivityLog(
            log_number=log_number,
            admin_id=admin_id,
            admin_name=admin_name,
            admin_email=admin_email,
            action_title=action_title,
            action_description=action_description,
            category=category,
            severity=severity,
            target_entity_id=target_entity_id,
            target_entity_type=target_entity_type,
            ip_address=ip_address,
        )
        return await self.repo.create(log)
