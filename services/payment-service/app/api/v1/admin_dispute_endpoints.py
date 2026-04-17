from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_publisher
from app.repositories.dispute_repo import DisputeNoteRepository, DisputeRepository
from app.repositories.refund_request_repo import RefundRequestRepository
from app.schemas.admin_dispute import (
    ApproveDisputeRequest,
    CreateDisputeNoteRequest,
    CreateDisputeRequest,
    DisputeDetailResponse,
    DisputeKPIsResponse,
    DisputeListItem,
    DisputeListResponse,
    DisputeNoteItem,
    RejectDisputeRequest,
)
from app.services.admin_dispute_service import AdminDisputeService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> AdminDisputeService:
    return AdminDisputeService(
        dispute_repo=DisputeRepository(session),
        note_repo=DisputeNoteRepository(session),
        refund_repo=RefundRequestRepository(session),
        publisher=publisher,
    )


@router.get(
    "/disputes/kpis",
    response_model=StandardResponse[DisputeKPIsResponse],
)
async def get_dispute_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisputeService = Depends(_get_service),
):
    """Get dispute KPI cards."""
    data = await service.get_dispute_kpis()
    return StandardResponse(data=DisputeKPIsResponse(**data))


@router.get(
    "/disputes",
    response_model=StandardResponse[DisputeListResponse],
)
async def get_disputes(
    status: str | None = Query(default=None, description="all|under_review|approved|rejected"),
    dispute_type: str | None = Query(default=None, description="fare_dispute|refund_request|trip_fraud"),
    search: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisputeService = Depends(_get_service),
):
    """List disputes with status tabs and search."""
    status_filter = status if status and status != "all" else None
    disputes, total = await service.get_disputes(
        status_filter=status_filter,
        dispute_type_filter=dispute_type,
        search=search,
        page=page,
        limit=page_size,
    )
    return StandardResponse(
        data=DisputeListResponse(
            items=[DisputeListItem.model_validate(d) for d in disputes],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/disputes",
    response_model=StandardResponse[DisputeDetailResponse],
)
async def create_dispute(
    body: CreateDisputeRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisputeService = Depends(_get_service),
):
    """Create a new dispute."""
    dispute = await service.create_dispute(body.model_dump())
    return StandardResponse(
        data=DisputeDetailResponse.model_validate(dispute),
        message="Dispute created successfully",
    )


@router.get(
    "/disputes/{dispute_id}",
    response_model=StandardResponse[DisputeDetailResponse],
)
async def get_dispute_detail(
    dispute_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisputeService = Depends(_get_service),
):
    """Get dispute detail for modal."""
    dispute = await service.get_dispute_detail(dispute_id)
    if not dispute:
        raise HTTPException(status_code=404, detail="Dispute not found")
    return StandardResponse(data=DisputeDetailResponse.model_validate(dispute))


@router.put(
    "/disputes/{dispute_id}/approve",
    response_model=StandardResponse[DisputeDetailResponse],
)
async def approve_dispute(
    dispute_id: UUID,
    body: ApproveDisputeRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisputeService = Depends(_get_service),
):
    """Approve dispute. Optionally creates a refund request."""
    try:
        # Get admin name from user claims (we don't have full_name, use email)
        admin_name = user.email or "Admin"
        dispute = await service.approve_dispute(
            dispute_id=dispute_id,
            admin_id=user.id,
            admin_name=admin_name,
            decision_note=body.decision_note,
            create_refund=body.create_refund,
            refund_amount=body.refund_amount,
        )
        return StandardResponse(
            data=DisputeDetailResponse.model_validate(dispute),
            message="Dispute approved",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/disputes/{dispute_id}/reject",
    response_model=StandardResponse[DisputeDetailResponse],
)
async def reject_dispute(
    dispute_id: UUID,
    body: RejectDisputeRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisputeService = Depends(_get_service),
):
    """Reject dispute with decision note."""
    try:
        # Get admin name from user claims (we don't have full_name, use email)
        admin_name = user.email or "Admin"
        dispute = await service.reject_dispute(
            dispute_id=dispute_id,
            admin_id=user.id,
            admin_name=admin_name,
            decision_note=body.decision_note,
        )
        return StandardResponse(
            data=DisputeDetailResponse.model_validate(dispute),
            message="Dispute rejected",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Notes ──


@router.post(
    "/disputes/{dispute_id}/notes",
    response_model=StandardResponse[DisputeNoteItem],
)
async def add_dispute_note(
    dispute_id: UUID,
    body: CreateDisputeNoteRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisputeService = Depends(_get_service),
):
    """Add a note to a dispute."""
    try:
        # Get admin name from user claims (we don't have full_name, use email)
        admin_name = user.email or "Admin"
        note = await service.add_note(
            dispute_id=dispute_id,
            admin_id=user.id,
            admin_name=admin_name,
            note_text=body.note,
        )
        return StandardResponse(
            data=DisputeNoteItem.model_validate(note),
            message="Note added",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/disputes/{dispute_id}/notes/{note_id}",
    response_model=StandardResponse[dict],
)
async def delete_dispute_note(
    dispute_id: UUID,
    note_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminDisputeService = Depends(_get_service),
):
    """Delete a dispute note."""
    deleted = await service.delete_note(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return StandardResponse(data={}, message="Note deleted")
