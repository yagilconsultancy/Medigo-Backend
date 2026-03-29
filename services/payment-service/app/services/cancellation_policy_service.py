import logging
import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.cancellation_policy_repo import CancellationPolicyRepository
from app.repositories.pricing_change_log_repo import PricingChangeLogRepository

logger = logging.getLogger(__name__)


class CancellationPolicyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CancellationPolicyRepository(session)
        self.log_repo = PricingChangeLogRepository(session)

    async def get_kpis(self) -> dict:
        service_types = await self.repo.count_service_types()
        fee_tiers = await self.repo.count_fee_tiers()
        max_fee = await self.repo.max_fee()
        return {
            "service_type_count": service_types,
            "fee_tier_count": fee_tiers,
            "max_fee": max_fee,
            "free_cancellation_window": "24+ hours",
        }

    async def get_all(self) -> dict:
        policies = await self.repo.get_all(active_only=True)
        matrix = [self._to_dict(p) for p in policies]

        by_type: dict[str, list] = defaultdict(list)
        for p in policies:
            by_type[p.service_type].append(self._to_dict(p))

        by_service_type = [
            {"service_type": st, "policies": items}
            for st, items in by_type.items()
        ]

        return {"matrix": matrix, "by_service_type": by_service_type}

    async def bulk_update(self, updates: list[dict], admin_id: uuid.UUID, admin_name: str) -> int:
        count = await self.repo.bulk_update(updates)

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "cancellation",
            "change_description": f"Updated {count} cancellation policy entries",
        })

        return count

    def _to_dict(self, p) -> dict:
        return {
            "id": p.id,
            "service_type": p.service_type,
            "cancellation_window": p.cancellation_window,
            "fee": p.fee,
            "who_receives": p.who_receives,
            "notes": p.notes,
            "sort_order": p.sort_order,
            "is_active": p.is_active,
        }
