from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_publisher
from app.repositories.business_repo import BusinessRepository
from app.repositories.invitation_repo import InvitationRepository
from app.schemas.business import (
    BusinessCreate,
    BusinessResponse,
    BusinessUpdate,
    InvitationResponse,
    InviteDriverRequest,
)
from app.services.business_service import BusinessService
from mediride_common.auth.dependencies import get_current_user, require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import PaginatedResponse, StandardResponse

router = APIRouter(prefix="/businesses")


def _get_business_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> BusinessService:
    return BusinessService(
        BusinessRepository(session),
        InvitationRepository(session),
        publisher,
    )


@router.post("", response_model=StandardResponse[BusinessResponse])
async def create_business(
    request: BusinessCreate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: BusinessService = Depends(_get_business_service),
):
    business = await service.create_business(
        created_by=user.id, **request.model_dump()
    )
    return StandardResponse(
        data=BusinessResponse.model_validate(business),
        message="Business created",
    )


@router.get("", response_model=PaginatedResponse[BusinessResponse])
async def list_businesses(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: BusinessService = Depends(_get_business_service),
):
    offset = (page - 1) * limit
    businesses, total = await service.list_businesses(offset, limit)
    return PaginatedResponse(
        data=[BusinessResponse.model_validate(b) for b in businesses],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.get("/{business_id}", response_model=StandardResponse[BusinessResponse])
async def get_business(
    business_id: UUID,
    user: UserClaims = Depends(
        require_role([UserRole.ADMIN, UserRole.BUSINESS])
    ),
    service: BusinessService = Depends(_get_business_service),
):
    business = await service.get_business(business_id)
    return StandardResponse(data=BusinessResponse.model_validate(business))


@router.put("/{business_id}", response_model=StandardResponse[BusinessResponse])
async def update_business(
    business_id: UUID,
    request: BusinessUpdate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN, UserRole.BUSINESS])),
    service: BusinessService = Depends(_get_business_service),
):
    update_data = request.model_dump(exclude_unset=True)
    business = await service.update_business(business_id, **update_data)
    return StandardResponse(
        data=BusinessResponse.model_validate(business),
        message="Business updated",
    )


# Driver Invitations
@router.post(
    "/{business_id}/invitations",
    response_model=StandardResponse[InvitationResponse],
)
async def invite_driver(
    business_id: UUID,
    request: InviteDriverRequest,
    user: UserClaims = Depends(
        require_role([UserRole.ADMIN, UserRole.BUSINESS])
    ),
    service: BusinessService = Depends(_get_business_service),
):
    invitation = await service.invite_driver(business_id, request.email, user.id)
    return StandardResponse(
        data=InvitationResponse.model_validate(invitation),
        message="Driver invitation sent",
    )


@router.get(
    "/{business_id}/invitations",
    response_model=PaginatedResponse[InvitationResponse],
)
async def list_invitations(
    business_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: UserClaims = Depends(
        require_role([UserRole.ADMIN, UserRole.BUSINESS])
    ),
    service: BusinessService = Depends(_get_business_service),
):
    offset = (page - 1) * limit
    invitations, total = await service.list_invitations(business_id, offset, limit)
    return PaginatedResponse(
        data=[InvitationResponse.model_validate(i) for i in invitations],
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.delete(
    "/{business_id}/invitations/{invitation_id}",
    response_model=StandardResponse,
)
async def revoke_invitation(
    business_id: UUID,
    invitation_id: UUID,
    user: UserClaims = Depends(
        require_role([UserRole.ADMIN, UserRole.BUSINESS])
    ),
    service: BusinessService = Depends(_get_business_service),
):
    await service.revoke_invitation(business_id, invitation_id)
    return StandardResponse(message="Invitation revoked")
