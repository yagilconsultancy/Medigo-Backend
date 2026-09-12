import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.auth_service_client import AuthServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.account_deletion_request_repo import (
    AccountDeletionRequestRepository,
)
from app.repositories.user_repo import UserRepository
from app.schemas.account_deletion_request import (
    AccountDeletionPublicResponse,
    AccountDeletionRequestCreate,
    AccountDeletionResendRequest,
    AccountDeletionVerifiedResponse,
    AccountDeletionVerifyRequest,
)
from app.services.account_deletion_request_service import (
    AccountDeletionRequestService,
)
from app.services.user_service import UserService
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.responses import StandardResponse

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


def _client_ip(request: Request) -> str | None:
    """Caller IP, preferring the gateway's forwarded header.

    Recorded for the audit trail only - never for access control, since
    X-Forwarded-For is client-settable.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host[:45] if request.client else None


@router.post(
    "/public/account-deletion/request",
    response_model=StandardResponse[AccountDeletionPublicResponse],
    status_code=202,
)
async def request_account_deletion(
    payload: AccountDeletionRequestCreate,
    request: Request,
    service: AccountDeletionRequestService = Depends(_get_service),
):
    """Public account deletion request - no authentication required.

    Backs https://getmedigo.com/medigo-delete-account, the deletion URL
    published on the Google Play listing. Emails a 6-digit code to the address
    given; the request only reaches the admin review queue once that code is
    confirmed.

    The response is identical whether or not the email belongs to an account,
    so this cannot be used to enumerate MediGo users.
    """
    if not payload.confirm_understanding:
        raise HTTPException(
            status_code=422,
            detail="You must confirm that account deletion is permanent to continue.",
        )

    message = await service.submit_request(
        full_name=payload.full_name.strip(),
        email=payload.email,
        phone=payload.phone,
        reason=payload.reason,
        ip_address=_client_ip(request),
    )
    return StandardResponse(
        data=AccountDeletionPublicResponse(message=message), message=message
    )


@router.post(
    "/public/account-deletion/verify",
    response_model=StandardResponse[AccountDeletionVerifiedResponse],
)
async def verify_account_deletion(
    payload: AccountDeletionVerifyRequest,
    service: AccountDeletionRequestService = Depends(_get_service),
):
    """Confirm the emailed code and hand the request to the admin queue."""
    deletion_request = await service.verify_code(
        email=payload.email, code=payload.code
    )
    return StandardResponse(
        data=AccountDeletionVerifiedResponse(
            reference=deletion_request.id,
            status=deletion_request.status,
            submitted_at=deletion_request.created_at,
        ),
        message="Deletion request verified and submitted for review",
    )


@router.post(
    "/public/account-deletion/resend-otp",
    response_model=StandardResponse[AccountDeletionPublicResponse],
    status_code=202,
)
async def resend_account_deletion_otp(
    payload: AccountDeletionResendRequest,
    service: AccountDeletionRequestService = Depends(_get_service),
):
    """Re-send the verification code, subject to a cooldown and a send cap."""
    message = await service.resend_code(email=payload.email)
    return StandardResponse(
        data=AccountDeletionPublicResponse(message=message), message=message
    )
