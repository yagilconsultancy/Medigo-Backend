import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride_package import RidePackage


class RidePackageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self, package_type: str | None = None) -> list[RidePackage]:
        q = select(RidePackage).order_by(RidePackage.sort_order)
        if package_type:
            q = q.where(RidePackage.package_type == package_type)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_by_id(self, package_id: uuid.UUID) -> RidePackage | None:
        q = select(RidePackage).where(RidePackage.id == package_id)
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> RidePackage:
        pkg = RidePackage(**data)
        self.session.add(pkg)
        await self.session.flush()
        await self.session.refresh(pkg)
        return pkg

    async def update(self, package_id: uuid.UUID, data: dict) -> RidePackage | None:
        obj = await self.get_by_id(package_id)
        if not obj:
            return None
        for k, v in data.items():
            setattr(obj, k, v)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def count_active(self) -> int:
        q = select(func.count()).select_from(RidePackage).where(RidePackage.is_active.is_(True))
        result = await self.session.execute(q)
        return result.scalar() or 0

    async def total_subscribers(self) -> int:
        q = select(func.coalesce(func.sum(RidePackage.active_subscribers), 0)).select_from(RidePackage).where(RidePackage.is_active.is_(True))
        result = await self.session.execute(q)
        return result.scalar() or 0

    async def count_types(self) -> int:
        q = select(func.count(func.distinct(RidePackage.package_type))).select_from(RidePackage).where(RidePackage.is_active.is_(True))
        result = await self.session.execute(q)
        return result.scalar() or 0
