import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.auth_service_client import AuthServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.models.account_deletion_request import AccountDeletionRequest
from app.repositories.account_deletion_request_repo import (
    AccountDeletionRequestRepository,
)
from app.repositories.user_repo import UserRepository
from app.schemas.account_deletion_request import (
    AccountDeletionKPIs,
    AccountDeletionRequestResponse,
    ApproveDeletionRequest,
    RejectDeletionRequest,
)
from app.services.account_deletion_request_service import (
    AccountDeletionRequestService,
)
from app.services.user_service import UserService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> AccountDeletionRequestService:
    user_repo = UserRepository(session)
    return AccountDeletionRequestService(
        request_repo=AccountDeletionRequestRepository(session),
        user_repo=user_repo,
        user_service=UserService(
            user_repo=user_repo,
            auth_client=AuthServiceClient(settings.AUTH_SERVICE_URL),
        ),
        publisher=publisher,
        settings=settings,
    )


def _to_response(
    request: AccountDeletionRequest,
) -> AccountDeletionRequestResponse:
    """Flatten the linked account onto the response.

    The admin's job is to check that the details typed into the public form
    match the account being deleted, so both sides have to be visible on the
    row without a second lookup.
    """
    response = AccountDeletionRequestResponse.model_validate(request)

    account = request.user
    if account is not None:
        response.account_email = account.email
        response.account_phone = account.phone
        response.account_name = (
            f"{account.first_name} {account.last_name}".strip() or None
        )
        response.account_role = account.role
        response.account_created_at = account.created_at
        response.account_deleted_at = account.deleted_at

    reviewer = request.reviewer
    if reviewer is not None:
        response.reviewer_name = (
            f"{reviewer.first_name} {reviewer.last_name}".strip() or None
        )

    return response


# --- Static routes first ---


@router.get(
    "/admin/account-deletion/requests/kpis",
    response_model=StandardResponse[AccountDeletionKPIs],
)
async def get_account_deletion_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AccountDeletionRequestService = Depends(_get_service),
):
    kpis = await service.get_kpis()
    return StandardResponse(data=kpis)


@router.get(
    "/admin/account-deletion/requests",
    response_model=PaginatedResponse[AccountDeletionRequestResponse],
)
async def list_account_deletion_requests(
    status: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AccountDeletionRequestService = Depends(_get_service),
):
    offset = (page - 1) * limit
    requests, total = await service.list_requests(
        status_filter=status, search=search, offset=offset, limit=limit
    )
    return PaginatedResponse(
        data=[_to_response(r) for r in requests],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


# --- Dynamic routes ---


@router.get(
    "/admin/account-deletion/requests/{request_id}",
    response_model=StandardResponse[AccountDeletionRequestResponse],
)
async def get_account_deletion_request(
    request_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AccountDeletionRequestService = Depends(_get_service),
):
    deletion_request = await service.get_request(request_id)
    return StandardResponse(data=_to_response(deletion_request))


@router.post(
    "/admin/account-deletion/requests/{request_id}/approve",
    response_model=StandardResponse[AccountDeletionRequestResponse],
)
async def approve_account_deletion_request(
    request_id: UUID,
    body: ApproveDeletionRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AccountDeletionRequestService = Depends(_get_service),
):
    """Approve a verified request: soft-deletes the profile and deactivates
    the account's login credentials."""
    deletion_request = await service.approve_request(
        request_id=request_id, admin_id=user.id, notes=body.notes
    )
    return StandardResponse(
        data=_to_response(deletion_request),
        message="Deletion request approved and the account has been deleted",
    )


@router.post(
    "/admin/account-deletion/requests/{request_id}/reject",
    response_model=StandardResponse[AccountDeletionRequestResponse],
)
async def reject_account_deletion_request(
    request_id: UUID,
    body: RejectDeletionRequest,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AccountDeletionRequestService = Depends(_get_service),
):
    deletion_request = await service.reject_request(
        request_id=request_id, admin_id=user.id, reason=body.reason
    )
    return StandardResponse(
        data=_to_response(deletion_request),
        message="Deletion request rejected",
    )
