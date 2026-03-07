from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ride_rating import RideRating


class RatingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, rating: RideRating) -> RideRating:
        self.session.add(rating)
        await self.session.flush()
        return rating

    async def get_by_ride_and_type(
        self, ride_id: UUID, rating_type: str
    ) -> RideRating | None:
        result = await self.session.execute(
            select(RideRating).where(
                RideRating.ride_id == ride_id,
                RideRating.rating_type == rating_type,
            )
        )
        return result.scalar_one_or_none()

    async def get_ratings_for_user(
        self, user_id: UUID, offset: int = 0, limit: int = 20
    ) -> tuple[list[RideRating], int]:
        base_query = select(RideRating).where(RideRating.rated_user_id == user_id)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(RideRating.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def get_average_rating(self, user_id: UUID) -> float:
        result = await self.session.execute(
            select(func.avg(RideRating.rating)).where(
                RideRating.rated_user_id == user_id
            )
        )
        return float(result.scalar_one() or 5.0)

    async def get_ratings_for_ride(self, ride_id: UUID) -> list[RideRating]:
        result = await self.session.execute(
            select(RideRating).where(RideRating.ride_id == ride_id)
        )
        return list(result.scalars().all())
