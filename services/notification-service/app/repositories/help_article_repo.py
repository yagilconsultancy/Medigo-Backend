from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.help_article import HelpArticle


class HelpArticleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_slug(self, slug: str) -> HelpArticle | None:
        result = await self.session.execute(
            select(HelpArticle).where(HelpArticle.slug == slug)
        )
        return result.scalar_one_or_none()

    async def get_by_category(self, category: str) -> list[HelpArticle]:
        result = await self.session.execute(
            select(HelpArticle)
            .where(HelpArticle.category == category)
            .order_by(HelpArticle.title)
        )
        return list(result.scalars().all())

    async def get_popular(self, limit: int = 10) -> list[HelpArticle]:
        result = await self.session.execute(
            select(HelpArticle)
            .where(HelpArticle.is_popular == True)
            .order_by(HelpArticle.view_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search(self, query: str) -> list[HelpArticle]:
        pattern = f"%{query}%"
        result = await self.session.execute(
            select(HelpArticle).where(
                or_(
                    HelpArticle.title.ilike(pattern),
                    HelpArticle.content.ilike(pattern),
                )
            )
            .order_by(HelpArticle.view_count.desc())
            .limit(20)
        )
        return list(result.scalars().all())

    async def get_categories(self) -> list[str]:
        result = await self.session.execute(
            select(HelpArticle.category).distinct().order_by(HelpArticle.category)
        )
        return [row[0] for row in result.all()]

    async def increment_view_count(self, article_id: UUID) -> None:
        from sqlalchemy import update
        await self.session.execute(
            update(HelpArticle)
            .where(HelpArticle.id == article_id)
            .values(view_count=HelpArticle.view_count + 1)
        )
