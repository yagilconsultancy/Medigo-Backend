"""Internal API endpoints for inter-service communication.

These endpoints are NOT exposed through the API gateway.
They are called directly by other services within the Docker network.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.business_repo import BusinessRepository
from app.repositories.invitation_repo import InvitationRepository
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal")


def _require_internal_service(
    x_internal_service: str | None = Header(None),
) -> str:
    """Verify the request comes from an internal service."""
    if not x_internal_service:
        raise HTTPException(status_code=403, detail="Internal access only")
    return x_internal_service


class AcceptInvitationRequest(BaseModel):
    token: str
    user_id: str


@router.get("/invitations/verify")
async def verify_invitation(
    token: str,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Verify a driver invitation token. Called by auth-service."""
    invitation_repo = InvitationRepository(session)
    business_repo = BusinessRepository(session)

    invitation = await invitation_repo.get_by_token(token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Invitation already used or revoked")

    if invitation.expires_at < utc_now():
        raise HTTPException(status_code=400, detail="Invitation has expired")

    business = await business_repo.get_by_id(invitation.business_id)
    business_name = business.name if business else "Unknown Business"

    return {
        "valid": True,
        "business_id": str(invitation.business_id),
        "business_name": business_name,
        "email": invitation.email,
        "invitation_id": str(invitation.id),
    }


@router.get("/users/{user_id}/profile")
async def get_user_profile_internal(
    user_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get user profile for ride enrichment. Called by ride-service."""
    from app.repositories.user_repo import UserRepository

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "role": user.role,
        "avatar_url": user.avatar_url,
        "is_active": user.is_active,
    }


@router.get("/drivers/{driver_id}/profile")
async def get_driver_profile_internal(
    driver_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get driver profile for ride enrichment. Called by ride-service."""
    from app.repositories.driver_repo import DriverRepository
    from app.repositories.user_repo import UserRepository

    user_repo = UserRepository(session)
    driver_repo = DriverRepository(session)

    user = await user_repo.get_by_id(driver_id)
    driver = await driver_repo.get_by_user_id(driver_id)

    if not user or not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    return {
        "user_id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "rating": float(driver.rating),
        "total_trips": driver.total_trips,
        "is_online": driver.is_online,
        "is_approved": driver.is_approved,
        "vehicle_type": driver.vehicle_type,
        "vehicle_make": driver.vehicle_make,
        "vehicle_model": driver.vehicle_model,
        "vehicle_plate": driver.vehicle_plate,
        "vehicle_color": driver.vehicle_color,
        "vehicle_year": driver.vehicle_year,
        "vehicle_photo_url": driver.vehicle_photo_url,
    }


class UpdateDriverStatsRequest(BaseModel):
    rating: float | None = None
    total_trips: int | None = None


@router.put("/drivers/{driver_id}/stats")
async def update_driver_stats_internal(
    driver_id: UUID,
    request: UpdateDriverStatsRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Update driver stats. Called by ride-service after rating/trip completion."""
    from app.repositories.driver_repo import DriverRepository

    driver_repo = DriverRepository(session)
    driver = await driver_repo.get_by_user_id(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    update_data = {}
    if request.rating is not None:
        update_data["rating"] = request.rating
    if request.total_trips is not None:
        update_data["total_trips"] = request.total_trips

    if update_data:
        await driver_repo.update(driver_id, **update_data)

    return {"updated": True, "driver_id": str(driver_id)}


@router.post("/invitations/accept")
async def accept_invitation(
    request: AcceptInvitationRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Mark an invitation as accepted. Called by auth-service after driver registration."""
    invitation_repo = InvitationRepository(session)

    invitation = await invitation_repo.get_by_token(request.token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    await invitation_repo.mark_accepted(invitation.id)
    logger.info(
        f"Invitation {invitation.id} accepted by user {request.user_id}"
    )

    return {"accepted": True, "invitation_id": str(invitation.id)}
