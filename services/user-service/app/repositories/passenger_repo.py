from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.passenger import Passenger


class PassengerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, passenger: Passenger) -> Passenger:
        self.session.add(passenger)
        await self.session.flush()
        return passenger

    async def get_by_id(self, passenger_id: UUID) -> Passenger | None:
        return await self.session.get(Passenger, passenger_id)

    async def list_by_user(self, user_id: UUID) -> list[Passenger]:
        result = await self.session.execute(
            select(Passenger)
            .where(Passenger.user_id == user_id)
            .order_by(Passenger.is_self.desc(), Passenger.created_at)
        )
        return list(result.scalars().all())

    async def update(self, passenger_id: UUID, **kwargs) -> None:
        await self.session.execute(
            update(Passenger).where(Passenger.id == passenger_id).values(**kwargs)
        )

    async def delete(self, passenger_id: UUID) -> None:
        await self.session.execute(
            delete(Passenger).where(Passenger.id == passenger_id)
        )
