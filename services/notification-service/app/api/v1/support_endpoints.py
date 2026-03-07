from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.support_ticket import SupportTicket
from app.repositories.help_article_repo import HelpArticleRepository
from app.repositories.support_ticket_repo import SupportTicketRepository
from app.schemas.support import (
    CreateTicketRequest,
    HelpArticleResponse,
    HelpArticleSummary,
    SupportTicketResponse,
)
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


# ---- Help Articles ----

@router.get("/help/articles", response_model=StandardResponse[list[HelpArticleSummary]])
async def list_help_articles(
    category: str | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_db),
):
    repo = HelpArticleRepository(session)
    if search:
        articles = await repo.search(search)
    elif category:
        articles = await repo.get_by_category(category)
    else:
        articles = await repo.get_popular()
    return StandardResponse(
        data=[HelpArticleSummary.model_validate(a) for a in articles],
    )


@router.get("/help/articles/{slug}", response_model=StandardResponse[HelpArticleResponse])
async def get_help_article(
    slug: str,
    session: AsyncSession = Depends(get_db),
):
    repo = HelpArticleRepository(session)
    article = await repo.get_by_slug(slug)
    if not article:
        from mediride_common.exceptions import NotFoundError
        raise NotFoundError("Article not found")
    await repo.increment_view_count(article.id)
    return StandardResponse(data=HelpArticleResponse.model_validate(article))


@router.get("/help/categories", response_model=StandardResponse[list[str]])
async def get_help_categories(
    session: AsyncSession = Depends(get_db),
):
    repo = HelpArticleRepository(session)
    categories = await repo.get_categories()
    return StandardResponse(data=categories)


# ---- Support Tickets ----

@router.post("/support/tickets", response_model=StandardResponse[SupportTicketResponse])
async def create_support_ticket(
    body: CreateTicketRequest,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = SupportTicketRepository(session)
    ticket = SupportTicket(
        user_id=user.id,
        subject=body.subject,
        category=body.category,
        description=body.description,
        priority=body.priority,
    )
    ticket = await repo.create(ticket)
    return StandardResponse(
        data=SupportTicketResponse.model_validate(ticket),
        message="Support ticket created",
    )


@router.get("/support/tickets", response_model=PaginatedResponse[SupportTicketResponse])
async def list_my_tickets(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = SupportTicketRepository(session)
    offset = (page - 1) * limit
    tickets, total = await repo.get_by_user(user.id, offset, limit)
    return PaginatedResponse(
        data=[SupportTicketResponse.model_validate(t) for t in tickets],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )
