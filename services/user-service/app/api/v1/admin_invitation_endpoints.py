from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_publisher
from app.repositories.admin_invitation_repo import AdminInvitationRepository
from app.repositories.admin_role_repo import AdminRoleRepository
from app.repositories.user_repo import UserRepository
from app.schemas.admin_invitation import (
    AdminInvitationResponse,
    AdminInviteRequest,
    AdminInviteSuccessResponse,
)
from app.services.admin_invitation_service import AdminInvitationService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> AdminInvitationService:
    return AdminInvitationService(
        invitation_repo=AdminInvitationRepository(session),
        user_repo=UserRepository(session),
        admin_role_repo=AdminRoleRepository(session),
        publisher=publisher,
    )


@router.post(
    "/admin/admins/invite",
    response_model=StandardResponse[AdminInviteSuccessResponse],
    status_code=201,
)
async def invite_admin(
    body: AdminInviteRequest,
    admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvitationService = Depends(_get_service),
):
    """Send an admin invitation email."""
    invitation = await service.send_invitation(
        email=body.email,
        full_name=body.full_name,
        role_name=body.role_name,
        invited_by=admin.id,
    )
    return StandardResponse(
        data=AdminInviteSuccessResponse(invitation_id=invitation.id),
        message="Admin invitation sent successfully",
    )


@router.get(
    "/admin/admins/invitations",
    response_model=PaginatedResponse[AdminInvitationResponse],
)
async def list_pending_invitations(
    page: int = 1,
    limit: int = 20,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvitationService = Depends(_get_service),
):
    """List all pending admin invitations."""
    offset = (page - 1) * limit
    invitations, total = await service.list_pending_invitations(offset, limit)
    return PaginatedResponse(
        data=[AdminInvitationResponse(**inv) for inv in invitations],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit if total > 0 else 0,
    )


@router.delete(
    "/admin/admins/invitations/{invitation_id}",
    response_model=StandardResponse[dict],
)
async def revoke_invitation(
    invitation_id: UUID,
    _admin: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: AdminInvitationService = Depends(_get_service),
):
    """Revoke a pending admin invitation."""
    await service.revoke_invitation(invitation_id)
    return StandardResponse(
        data={"invitation_id": invitation_id},
        message="Invitation revoked successfully",
    )
