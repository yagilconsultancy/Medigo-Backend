from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.login_record import LoginRecord
from app.repositories.login_record_repo import LoginRecordRepository


class LoginHistoryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LoginRecordRepository(session)

    async def get_kpis(self) -> dict:
        return await self.repo.get_kpi_counts()

    async def list_records(
        self,
        success: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        offset = (page - 1) * page_size
        records, total = await self.repo.list_records(
            success=success, search=search, offset=offset, limit=page_size
        )
        items = []
        for r in records:
            items.append({
                "id": r.id,
                "admin_name": r.admin_name,
                "admin_email": r.admin_email,
                "ip_address": r.ip_address,
                "device_info": r.device_info,
                "location": r.location,
                "success": r.success,
                "failure_reason": r.failure_reason,
                "is_suspicious": r.is_suspicious,
                "created_at": r.created_at,
            })
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def record_login(
        self,
        user_id: UUID,
        admin_name: str,
        admin_email: str,
        ip_address: str,
        device_info: str,
        location: str | None = None,
        success: bool = True,
        failure_reason: str | None = None,
        is_suspicious: bool = False,
    ) -> LoginRecord:
        record = LoginRecord(
            user_id=user_id,
            admin_name=admin_name,
            admin_email=admin_email,
            ip_address=ip_address,
            device_info=device_info,
            location=location,
            success=success,
            failure_reason=failure_reason,
            is_suspicious=is_suspicious,
        )
        return await self.repo.create(record)
