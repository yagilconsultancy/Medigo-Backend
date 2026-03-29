import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.pricing_change_log_repo import PricingChangeLogRepository

logger = logging.getLogger(__name__)


class PricingLogService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PricingChangeLogRepository(session)

    async def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
        search: str | None = None,
    ) -> dict:
        items, total = await self.repo.get_paginated(
            page=page, page_size=page_size, category=category, search=search
        )
        return {
            "items": [self._to_dict(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def export(self, category: str | None = None) -> dict:
        items = await self.repo.get_all_for_export(category=category)
        return {
            "items": [self._to_dict(i) for i in items],
            "total": len(items),
        }

    def _to_dict(self, log) -> dict:
        return {
            "id": log.id,
            "log_number": log.log_number,
            "admin_id": log.admin_id,
            "admin_name": log.admin_name,
            "category": log.category,
            "city": log.city,
            "change_description": log.change_description,
            "before_value": log.before_value,
            "after_value": log.after_value,
            "created_at": log.created_at,
        }
