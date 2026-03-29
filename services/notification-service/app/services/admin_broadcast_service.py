from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_broadcast import AdminBroadcast
from app.repositories.admin_broadcast_repo import AdminBroadcastRepository

# KPI label mappings per broadcast type
_KPI_LABELS = {
    "system": ("maintenance", "Maintenance", "security_alert", "Security Alerts"),
    "rider": ("announcement", "Announcements", "promotion", "Promotions"),
    "driver": ("surge_alert", "Surge Alerts", "payout_notice", "Payout Notices"),
    "fleet": ("revenue_report", "Revenue Reports", "fleet_policy_update", "Policy Updates"),
}


class AdminBroadcastService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = AdminBroadcastRepository(session)

    async def get_kpis(self, broadcast_type: str) -> dict:
        total = await self.repo.count_by_type(broadcast_type)
        delivered = await self.repo.sum_delivered(broadcast_type)

        labels = _KPI_LABELS.get(broadcast_type, ("", "", "", ""))
        cat1_type, cat1_label, cat2_type, cat2_label = labels
        cat1 = await self.repo.count_by_notification_type(broadcast_type, cat1_type) if cat1_type else 0
        cat2 = await self.repo.count_by_notification_type(broadcast_type, cat2_type) if cat2_type else 0

        return {
            "total_sent": total,
            "category_1_count": cat1,
            "category_1_label": cat1_label,
            "category_2_count": cat2,
            "category_2_label": cat2_label,
            "total_delivered": delivered,
        }

    async def get_history(
        self,
        broadcast_type: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        offset = (page - 1) * page_size
        items, total = await self.repo.get_by_type(
            broadcast_type=broadcast_type, offset=offset, limit=page_size,
        )
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def send_broadcast(
        self,
        broadcast_type: str,
        data: dict,
        admin_id: UUID,
    ) -> AdminBroadcast:
        broadcast = AdminBroadcast(
            broadcast_type=broadcast_type,
            notification_type=data["notification_type"],
            title=data["title"],
            message=data["message"],
            audience_segment=data["audience_segment"],
            sent_to_count=data.get("sent_to_count", 0),
            delivered_count=data.get("sent_to_count", 0),
            created_by_id=admin_id,
        )
        return await self.repo.create(broadcast)
