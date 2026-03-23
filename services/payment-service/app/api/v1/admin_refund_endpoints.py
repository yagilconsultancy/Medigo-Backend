from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.stripe_client import StripeClient
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher, get_stripe_client
from app.repositories.refund_request_repo import RefundRequestRepository
from app.repositories.transaction_repo import TransactionRepository
from app.schemas.admin_refund import (
    ApproveRefundRequest,
    CreateRefundRequest,
    RefundDetailResponse,
    RefundKPIsResponse,
    RefundRequestListItem,
    RejectRefundRequest,
)
from app.services.admin_refund_service import AdminRefundService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    stripe: StripeClient = Depends(get_stripe_client),
    publisher: EventPublisher = Depends(get_publisher),
) -> AdminRefundService:
    return AdminRefundService(
        refund_repo=RefundRequestRepository(session),
        tx_repo=TransactionRepository(session),
        stripe_client=stripe,
        user_client=UserServiceClient(settings.USER_SERVICE_URL),
        publisher=publisher,
    )


@router.get(
    "/refunds/kpis",
    response_model=StandardResponse[RefundKPIsResponse],
)
async def get_refund_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRefundService = Depends(_get_service),
):
    """Get refund KPI cards."""
    data = await service.get_refund_kpis()
    return StandardResponse(data=RefundKPIsResponse(**data))


# Static paths before /{refund_id}
@router.get(
    "/refunds",
    response_model=PaginatedResponse[RefundRequestListItem],
)
async def get_refund_requests(
    status: str | None = Query(default=None, description="all|pending|approved|rejected"),
    search: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRefundService = Depends(_get_service),
):
    """List refund requests with status tabs and search."""
    status_filter = status if status and status != "all" else None
    items, total = await service.get_refund_requests(status_filter, search, page, limit)
    return PaginatedResponse(
        data=[RefundRequestListItem(**item) for item in items],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.post(
    "/refunds",
    response_model=StandardResponse[RefundDetailResponse],
)
async def create_refund_request(
    body: CreateRefundRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRefundService = Depends(_get_service),
):
    """Create a refund request."""
    refund = await service.create_refund_request(body.model_dump())
    detail = await service.get_refund_detail(refund.id)
    return StandardResponse(data=RefundDetailResponse(**detail))


@router.get(
    "/refunds/{refund_id}",
    response_model=StandardResponse[RefundDetailResponse],
)
async def get_refund_detail(
    refund_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRefundService = Depends(_get_service),
):
    """Get refund detail for side panel."""
    detail = await service.get_refund_detail(refund_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Refund request not found")
    return StandardResponse(data=RefundDetailResponse(**detail))


@router.put(
    "/refunds/{refund_id}/approve",
    response_model=StandardResponse[RefundDetailResponse],
)
async def approve_refund(
    refund_id: UUID,
    body: ApproveRefundRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRefundService = Depends(_get_service),
):
    """Approve refund (full or partial). Processes Stripe refund."""
    try:
        detail = await service.approve_refund(
            refund_id=refund_id,
            admin_id=user.id,
            decision_note=body.decision_note,
            is_partial=body.is_partial,
            partial_amount=body.partial_amount,
        )
        return StandardResponse(data=RefundDetailResponse(**detail))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/refunds/{refund_id}/reject",
    response_model=StandardResponse[RefundDetailResponse],
)
async def reject_refund(
    refund_id: UUID,
    body: RejectRefundRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminRefundService = Depends(_get_service),
):
    """Reject refund request with decision note."""
    try:
        detail = await service.reject_refund(
            refund_id=refund_id,
            admin_id=user.id,
            decision_note=body.decision_note,
        )
        return StandardResponse(data=RefundDetailResponse(**detail))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
