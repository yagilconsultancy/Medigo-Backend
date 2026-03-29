import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.pricing_change_log_repo import PricingChangeLogRepository
from app.repositories.ride_package_repo import RidePackageRepository

logger = logging.getLogger(__name__)


class RidePackageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RidePackageRepository(session)
        self.log_repo = PricingChangeLogRepository(session)

    async def get_kpis(self) -> dict:
        active = await self.repo.count_active()
        subscribers = await self.repo.total_subscribers()
        types = await self.repo.count_types()
        return {
            "active_count": active,
            "total_subscribers": subscribers,
            "type_count": types,
        }

    async def get_all(self, package_type: str | None = None) -> list[dict]:
        packages = await self.repo.get_all(package_type=package_type)
        return [self._to_dict(p) for p in packages]

    async def get_by_id(self, package_id: uuid.UUID) -> dict | None:
        pkg = await self.repo.get_by_id(package_id)
        if not pkg:
            return None
        return self._to_dict(pkg)

    async def create(self, data: dict, admin_id: uuid.UUID, admin_name: str) -> dict:
        data["created_by"] = admin_id
        pkg = await self.repo.create(data)

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "package",
            "change_description": f"Created package: {pkg.name}",
            "after_value": f"${pkg.price} / {pkg.ride_count or 'unlimited'} rides",
        })

        return self._to_dict(pkg)

    async def update(self, package_id: uuid.UUID, data: dict, admin_id: uuid.UUID, admin_name: str) -> dict | None:
        old = await self.repo.get_by_id(package_id)
        if not old:
            return None

        updated = await self.repo.update(package_id, data)

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "package",
            "change_description": f"Updated package: {updated.name}",
            "before_value": f"${old.price} / {old.ride_count or 'unlimited'} rides",
            "after_value": f"${updated.price} / {updated.ride_count or 'unlimited'} rides",
        })

        return self._to_dict(updated)

    async def toggle(self, package_id: uuid.UUID, admin_id: uuid.UUID, admin_name: str) -> dict | None:
        pkg = await self.repo.get_by_id(package_id)
        if not pkg:
            return None

        new_active = not pkg.is_active
        updated = await self.repo.update(package_id, {"is_active": new_active})

        await self.log_repo.create({
            "admin_id": admin_id,
            "admin_name": admin_name,
            "category": "package",
            "change_description": f"{'Activated' if new_active else 'Deactivated'} package: {updated.name}",
        })

        return self._to_dict(updated)

    def _to_dict(self, p) -> dict:
        return {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "package_type": p.package_type,
            "price": p.price,
            "ride_count": p.ride_count,
            "is_unlimited": p.is_unlimited,
            "discount_percent": p.discount_percent,
            "validity_days": p.validity_days,
            "is_active": p.is_active,
            "active_subscribers": p.active_subscribers,
            "sort_order": p.sort_order,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }
