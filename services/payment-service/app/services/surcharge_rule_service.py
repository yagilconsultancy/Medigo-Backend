import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.pricing_change_log_repo import PricingChangeLogRepository
from app.repositories.surcharge_rule_repo import SurchargeRuleRepository

logger = logging.getLogger(__name__)


class SurchargeRuleService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SurchargeRuleRepository(session)
        self.log_repo = PricingChangeLogRepository(session)

    async def get_kpis(self) -> dict:
        active = await self.repo.count_active()
        inactive = await self.repo.count_inactive()
        return {
            "active_count": active,
            "inactive_count": inactive,
            "total_count": active + inactive,
        }

    async def get_all(self) -> list[dict]:
        rules = await self.repo.get_all()
        return [self._to_dict(r) for r in rules]

    async def create(self, data: dict, admin_id: uuid.UUID, admin_name: str) -> dict:
        data["created_by"] = admin_id
        rule = await self.repo.create(data)

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "surcharge",
            "change_description": f"Created surcharge rule: {rule.name}",
            "after_value": f"{rule.surcharge_type} {rule.multiplier}x",
        })

        return self._to_dict(rule)

    async def update(self, rule_id: uuid.UUID, data: dict, admin_id: uuid.UUID, admin_name: str) -> dict | None:
        old = await self.repo.get_by_id(rule_id)
        if not old:
            return None

        old_value = f"{old.surcharge_type} {old.multiplier}x active={old.is_active}"
        updated = await self.repo.update(rule_id, data)

        desc = f"Updated surcharge rule: {updated.name}"
        if "is_active" in data and data["is_active"] != old.is_active:
            desc = f"{'Enabled' if data['is_active'] else 'Disabled'} surcharge rule: {updated.name}"

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "surcharge",
            "change_description": desc,
            "before_value": old_value,
            "after_value": f"{updated.surcharge_type} {updated.multiplier}x active={updated.is_active}",
        })

        return self._to_dict(updated)

    async def delete(self, rule_id: uuid.UUID, admin_id: uuid.UUID, admin_name: str) -> bool:
        old = await self.repo.get_by_id(rule_id)
        if not old:
            return False

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "surcharge",
            "change_description": f"Deleted surcharge rule: {old.name}",
            "before_value": f"{old.surcharge_type} {old.multiplier}x",
        })

        return await self.repo.delete(rule_id)

    def _to_dict(self, r) -> dict:
        return {
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "surcharge_type": r.surcharge_type,
            "multiplier": r.multiplier,
            "flat_amount": r.flat_amount,
            "schedule": r.schedule,
            "applies_to": r.applies_to,
            "is_active": r.is_active,
            "sort_order": r.sort_order,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
