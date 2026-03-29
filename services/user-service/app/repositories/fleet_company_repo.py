from uuid import UUID

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fleet import Fleet
from app.models.driver_profile import DriverProfile
from app.models.vehicle import Vehicle


class FleetCompanyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_fleets_with_counts(
        self,
        status_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        conditions = [Fleet.deleted_at.is_(None)]

        if status_filter == "active":
            conditions.append(Fleet.is_active.is_(True))
        elif status_filter == "inactive":
            conditions.append(Fleet.is_active.is_(False))

        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    Fleet.name.ilike(pattern),
                    Fleet.contact_person.ilike(pattern),
                    Fleet.email.ilike(pattern),
                    Fleet.city.ilike(pattern),
                )
            )

        # Subqueries for counts
        vehicle_count_sq = (
            select(func.count())
            .where(Vehicle.business_id == Fleet.id, Vehicle.deleted_at.is_(None))
            .correlate(Fleet)
            .scalar_subquery()
        )
        driver_count_sq = (
            select(func.count())
            .where(DriverProfile.business_id == Fleet.id)
            .correlate(Fleet)
            .scalar_subquery()
        )

        base_query = (
            select(
                Fleet,
                vehicle_count_sq.label("vehicle_count"),
                driver_count_sq.label("driver_count"),
            )
            .where(*conditions)
        )

        # Count total
        count_query = select(func.count()).select_from(
            select(Fleet.id).where(*conditions).subquery()
        )
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one()

        # Paginated results
        result = await self.session.execute(
            base_query
            .order_by(desc(Fleet.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = result.all()
        return [
            {
                "fleet": row[0],
                "vehicle_count": row[1] or 0,
                "driver_count": row[2] or 0,
            }
            for row in rows
        ], total

    async def get_fleet_kpis(self) -> dict:
        # Total and active fleets
        fleet_result = await self.session.execute(
            select(
                func.count().label("total_fleets"),
                func.count().filter(Fleet.is_active.is_(True)).label("active_fleets"),
            ).where(Fleet.deleted_at.is_(None))
        )
        fleet_row = fleet_result.one()

        # Total vehicles
        vehicle_result = await self.session.execute(
            select(func.count()).where(Vehicle.deleted_at.is_(None))
        )
        total_vehicles = vehicle_result.scalar_one()

        # Total drivers
        driver_result = await self.session.execute(
            select(func.count()).select_from(DriverProfile)
        )
        total_drivers = driver_result.scalar_one()

        return {
            "total_fleets": fleet_row.total_fleets,
            "active_fleets": fleet_row.active_fleets,
            "total_fleet_vehicles": total_vehicles,
            "fleet_drivers": total_drivers,
        }

    async def get_fleet_detail_with_counts(self, fleet_id: UUID) -> dict | None:
        vehicle_count_sq = (
            select(func.count())
            .where(Vehicle.business_id == Fleet.id, Vehicle.deleted_at.is_(None))
            .correlate(Fleet)
            .scalar_subquery()
        )
        driver_count_sq = (
            select(func.count())
            .where(DriverProfile.business_id == Fleet.id)
            .correlate(Fleet)
            .scalar_subquery()
        )

        result = await self.session.execute(
            select(
                Fleet,
                vehicle_count_sq.label("vehicle_count"),
                driver_count_sq.label("driver_count"),
            ).where(Fleet.id == fleet_id, Fleet.deleted_at.is_(None))
        )
        row = result.one_or_none()
        if not row:
            return None
        return {
            "fleet": row[0],
            "vehicle_count": row[1] or 0,
            "driver_count": row[2] or 0,
        }

    async def get_avg_driver_rating(self, fleet_id: UUID) -> float:
        result = await self.session.execute(
            select(func.avg(DriverProfile.rating)).where(
                DriverProfile.business_id == fleet_id
            )
        )
        avg = result.scalar_one()
        return round(float(avg), 2) if avg else 0.0
