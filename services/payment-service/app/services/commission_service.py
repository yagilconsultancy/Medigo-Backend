import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.commission_config_repo import CommissionConfigRepository
from app.repositories.pricing_change_log_repo import PricingChangeLogRepository

logger = logging.getLogger(__name__)


class CommissionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CommissionConfigRepository(session)
        self.log_repo = PricingChangeLogRepository(session)

    async def get_kpis(self) -> dict:
        config = await self.repo.get_active()
        if not config:
            return {
                "platform_percent": 0,
                "driver_percent": 0,
                "fleet_percent": 0,
                "caregiver_percent": 0,
                "reserve_percent": 0,
            }
        return {
            "platform_percent": config.platform_percent,
            "driver_percent": config.driver_percent,
            "fleet_percent": config.fleet_percent,
            "caregiver_percent": config.caregiver_percent,
            "reserve_percent": config.reserve_percent,
        }

    async def get_config(self) -> dict | None:
        config = await self.repo.get_active()
        if not config:
            return None
        return {
            "id": config.id,
            "platform_percent": config.platform_percent,
            "driver_percent": config.driver_percent,
            "fleet_percent": config.fleet_percent,
            "caregiver_percent": config.caregiver_percent,
            "reserve_percent": config.reserve_percent,
            "is_active": config.is_active,
            "version": config.version,
            "created_at": config.created_at,
        }

    async def update_config(self, data: dict, admin_id: uuid.UUID, admin_name: str) -> dict:
        old_config = await self.repo.get_active()
        old_value = None
        if old_config:
            old_value = (
                f"P:{old_config.platform_percent}% D:{old_config.driver_percent}% "
                f"F:{old_config.fleet_percent}% C:{old_config.caregiver_percent}% "
                f"R:{old_config.reserve_percent}%"
            )

        data["created_by"] = admin_id
        new_config = await self.repo.create_new_version(data)

        new_value = (
            f"P:{new_config.platform_percent}% D:{new_config.driver_percent}% "
            f"F:{new_config.fleet_percent}% C:{new_config.caregiver_percent}% "
            f"R:{new_config.reserve_percent}%"
        )

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "commission",
            "change_description": f"Updated commission split to v{new_config.version}",
            "before_value": old_value,
            "after_value": new_value,
        })

        return {
            "id": new_config.id,
            "platform_percent": new_config.platform_percent,
            "driver_percent": new_config.driver_percent,
            "fleet_percent": new_config.fleet_percent,
            "caregiver_percent": new_config.caregiver_percent,
            "reserve_percent": new_config.reserve_percent,
            "is_active": new_config.is_active,
            "version": new_config.version,
            "created_at": new_config.created_at,
        }
