from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_card import RateCard


class RateCardRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self) -> RateCard | None:
        result = await self.session.execute(
            select(RateCard).where(RateCard.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, card_id: UUID) -> RateCard | None:
        result = await self.session.execute(
            select(RateCard).where(RateCard.id == card_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, limit: int = 50, offset: int = 0) -> list[RateCard]:
        result = await self.session.execute(
            select(RateCard)
            .order_by(RateCard.version.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_next_version(self) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.max(RateCard.version), 0))
        )
        return result.scalar_one() + 1

    async def deactivate_all(self) -> None:
        result = await self.session.execute(
            select(RateCard).where(RateCard.is_active.is_(True))
        )
        for card in result.scalars().all():
            card.is_active = False

    async def create(self, rate_card: RateCard) -> RateCard:
        self.session.add(rate_card)
        await self.session.flush()
        return rate_card

    async def activate(self, card_id: UUID) -> RateCard | None:
        await self.deactivate_all()
        card = await self.get_by_id(card_id)
        if card:
            card.is_active = True
            await self.session.flush()
        return card
