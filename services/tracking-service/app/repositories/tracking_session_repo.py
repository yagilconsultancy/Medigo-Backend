from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tracking_session import TrackingSession
from mediride_common.schemas.enums import TrackingSessionStatus
from mediride_common.utils import utc_now


class TrackingSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, session_obj: TrackingSession) -> TrackingSession:
        self.session.add(session_obj)
        await self.session.flush()
        return session_obj

    async def get_by_id(self, session_id: UUID) -> TrackingSession | None:
        result = await self.session.execute(
            select(TrackingSession).where(TrackingSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_ride_id(self, ride_id: UUID) -> TrackingSession | None:
        result = await self.session.execute(
            select(TrackingSession).where(
                TrackingSession.ride_id == ride_id,
                TrackingSession.status == TrackingSessionStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_driver_id(self, driver_id: UUID) -> TrackingSession | None:
        result = await self.session.execute(
            select(TrackingSession).where(
                TrackingSession.driver_id == driver_id,
                TrackingSession.status == TrackingSessionStatus.ACTIVE,
            )
        )
        return result.scalar_one_or_none()

    async def update_location(
        self,
        session_id: UUID,
        latitude: float,
        longitude: float,
        heading: float | None = None,
        speed: float | None = None,
        eta_minutes: float | None = None,
        distance_remaining_miles: float | None = None,
    ) -> None:
        values: dict = {
            "current_latitude": latitude,
            "current_longitude": longitude,
            "updated_at": utc_now(),
        }
        if heading is not None:
            values["current_heading"] = heading
        if speed is not None:
            values["current_speed"] = speed
        if eta_minutes is not None:
            values["eta_minutes"] = eta_minutes
        if distance_remaining_miles is not None:
            values["distance_remaining_miles"] = distance_remaining_miles

        await self.session.execute(
            update(TrackingSession)
            .where(TrackingSession.id == session_id)
            .values(**values)
        )

    async def end_session(self, session_id: UUID) -> None:
        await self.session.execute(
            update(TrackingSession)
            .where(TrackingSession.id == session_id)
            .values(status=TrackingSessionStatus.COMPLETED, completed_at=utc_now(), updated_at=utc_now())
        )

    # ---- Admin bulk queries ----

    async def get_all_active_sessions(self) -> list[TrackingSession]:
        result = await self.session.execute(
            select(TrackingSession).where(TrackingSession.status == TrackingSessionStatus.ACTIVE)
            .order_by(TrackingSession.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_active_count(self) -> int:
        result = await self.session.execute(
            select(func.count()).where(TrackingSession.status == TrackingSessionStatus.ACTIVE)
        )
        return result.scalar_one()

    async def get_arriving_soon_count(self, threshold: float = 5.0) -> int:
        result = await self.session.execute(
            select(func.count()).where(
                TrackingSession.status == TrackingSessionStatus.ACTIVE,
                TrackingSession.eta_minutes.isnot(None),
                TrackingSession.eta_minutes <= threshold,
            )
        )
        return result.scalar_one()

    async def get_avg_speed(self) -> float | None:
        result = await self.session.execute(
            select(func.avg(TrackingSession.current_speed)).where(
                TrackingSession.status == TrackingSessionStatus.ACTIVE,
                TrackingSession.current_speed.isnot(None),
            )
        )
        val = result.scalar_one()
        return float(val) if val is not None else None

    async def get_completed_today_count(self) -> int:
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count()).where(
                TrackingSession.status == TrackingSessionStatus.COMPLETED,
                TrackingSession.completed_at >= today_start,
            )
        )
        return result.scalar_one()
