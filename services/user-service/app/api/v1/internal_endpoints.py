"""Internal API endpoints for inter-service communication.

These endpoints are NOT exposed through the API gateway.
They are called directly by other services within the Docker network.
"""
import logging
import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.fleet_repo import FleetRepository
from app.repositories.invitation_repo import InvitationRepository
from app.repositories.settings_repo import SettingsRepository
from app.repositories.user_repo import UserRepository
from app.services.user_service import UserService
from mediride_common.schemas.enums import UserRole
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


class CreateGuestRiderRequest(BaseModel):
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, min_length=10, max_length=20)
    full_name: str | None = Field(None, min_length=1, max_length=200)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        if self.full_name and not (self.first_name and self.last_name):
            parts = self.full_name.strip().split(None, 1)
            self.first_name = self.first_name or parts[0]
            self.last_name = self.last_name or (parts[1] if len(parts) > 1 else "")
        return self


@router.get("/invitations/verify")
async def verify_invitation(
    token: str,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Verify a driver invitation token. Called by auth-service."""
    invitation_repo = InvitationRepository(session)
    fleet_repo = FleetRepository(session)

    invitation = await invitation_repo.get_by_token(token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Invitation already used or revoked")

    if invitation.expires_at < utc_now():
        raise HTTPException(status_code=400, detail="Invitation has expired")

    fleet = await fleet_repo.get_by_id(invitation.business_id)
    fleet_name = fleet.name if fleet else "Unknown Fleet"

    return {
        "valid": True,
        "business_id": str(invitation.business_id),
        "fleet_name": fleet_name,
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
        "is_guest": user.is_guest,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/users/{user_id}/settings")
async def get_user_settings_internal(
    user_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get user settings for internal notification decisions."""
    settings_repo = SettingsRepository(session)
    user_settings = await settings_repo.get_or_create(user_id)
    return {
        "user_id": str(user_id),
        "email_ride_receipts": user_settings.email_ride_receipts,
        "push_ride_updates": user_settings.push_ride_updates,
        "sms_ride_updates": user_settings.sms_ride_updates,
    }


@router.post("/guest-riders")
async def create_guest_rider_internal(
    body: CreateGuestRiderRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Create a lightweight guest rider profile. Called by ride-service."""
    service = UserService(UserRepository(session))
    user = await service.create_profile_from_registration(
        user_id=uuid.uuid4(),
        email=body.email,
        phone=body.phone,
        first_name=body.first_name,
        last_name=body.last_name,
        role=UserRole.RIDER,
        is_guest=True,
    )
    return {
        "user_id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "role": user.role,
        "is_guest": user.is_guest,
    }


@router.get("/users/batch")
async def batch_get_users_internal(
    user_ids: str = "",
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Batch get user details (id, first_name, last_name). Called by ride-service for enrichment."""
    from app.models.user import User

    if not user_ids.strip():
        return {"users": []}

    ids = [UUID(u.strip()) for u in user_ids.split(",") if u.strip()]

    result = await session.execute(
        select(User).where(User.id.in_(ids))
    )
    users = result.scalars().all()

    return {
        "users": [
            {
                "id": str(u.id),
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email,
                "phone": u.phone,
                "avatar_url": u.avatar_url,
                "is_guest": u.is_guest,
            }
            for u in users
        ]
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
        "business_id": str(driver.business_id) if driver.business_id else None,
        "rating": float(driver.rating),
        "total_trips": driver.total_trips,
        "is_online": driver.is_online,
        "is_approved": driver.is_approved,
        "account_status": getattr(driver, "account_status", None),
        "specialty": getattr(driver, "specialty", None),
        "service_capabilities": getattr(driver, "service_capabilities", None) or [],
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


@router.get("/fleets/{fleet_id}")
async def get_fleet_internal(
    fleet_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get fleet details. Called by ride-service for assignment validation."""
    fleet_repo = FleetRepository(session)
    fleet = await fleet_repo.get_by_id(fleet_id)
    if not fleet:
        raise HTTPException(status_code=404, detail="Fleet not found")

    return {
        "id": str(fleet.id),
        "name": fleet.name,
        "type": fleet.type,
        "is_active": fleet.is_active,
        "email": fleet.email,
        "phone": fleet.phone,
    }


@router.get("/fleets/{fleet_id}/drivers")
async def get_fleet_drivers_internal(
    fleet_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get approved drivers for a fleet. Called by ride-service for driver assignment."""
    from app.repositories.driver_repo import DriverRepository

    driver_repo = DriverRepository(session)
    drivers, _ = await driver_repo.list_by_fleet(
        fleet_id, offset=0, limit=500, is_approved=True
    )
    return {
        "drivers": [
            {
                "user_id": str(d.user_id),
                "is_approved": d.is_approved,
                "is_online": d.is_online,
                "vehicle_type": d.vehicle_type,
                "business_id": str(d.business_id),
            }
            for d in drivers
        ]
    }


@router.get("/drivers/available")
async def get_available_drivers_internal(
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get all approved drivers for admin assignment. Called by ride-service."""
    from app.repositories.driver_repo import DriverRepository
    from app.repositories.user_repo import UserRepository

    driver_repo = DriverRepository(session)
    user_repo = UserRepository(session)

    drivers = await driver_repo.get_available_drivers()

    result = []
    for d in drivers:
        user = await user_repo.get_by_id(d.user_id)
        fleet = None
        if d.business_id:
            fleet = await FleetRepository(session).get_by_id(d.business_id)

        result.append({
            "user_id": str(d.user_id),
            "first_name": user.first_name if user else "",
            "last_name": user.last_name if user else "",
            "name": f"{user.first_name} {user.last_name}" if user else "Unknown",
            "phone": user.phone if user else None,
            "avatar_url": user.avatar_url if user else None,
            "rating": float(d.rating),
            "total_trips": d.total_trips,
            "is_online": d.is_online,
            "vehicle_type": d.vehicle_type,
            "vehicle_make": d.vehicle_make,
            "vehicle_model": d.vehicle_model,
            "vehicle_year": d.vehicle_year,
            "vehicle_plate": d.vehicle_plate,
            "specialty": getattr(d, "specialty", None),
            "fleet_name": fleet.name if fleet else None,
            "business_id": str(d.business_id) if d.business_id else None,
        })

    return {"drivers": result}


@router.get("/drivers/with-details")
async def get_drivers_with_details(
    driver_ids: str = "",
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Batch get driver details (name, specialty, fleet). Called by payment-service."""
    from app.repositories.driver_repo import DriverRepository
    from app.repositories.user_repo import UserRepository

    if not driver_ids.strip():
        return {"drivers": []}

    ids = [UUID(d.strip()) for d in driver_ids.split(",") if d.strip()]
    driver_repo = DriverRepository(session)
    user_repo = UserRepository(session)
    fleet_repo = FleetRepository(session)

    drivers = []
    for driver_id in ids:
        user = await user_repo.get_by_id(driver_id)
        driver = await driver_repo.get_by_user_id(driver_id)
        if user and driver:
            fleet = await fleet_repo.get_by_id(driver.business_id) if driver.business_id else None
            drivers.append({
                "driver_id": str(driver_id),
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": user.avatar_url,
                "specialty": getattr(driver, "specialty", None),
                "account_status": getattr(driver, "account_status", None),
                "fleet_name": fleet.name if fleet else None,
                "business_id": str(driver.business_id) if driver.business_id else None,
            })

    return {"drivers": drivers}


@router.get("/fleets/with-vehicle-counts")
async def get_fleets_with_vehicle_counts(
    fleet_ids: str = "",
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Batch get fleet names + vehicle counts. Called by ride-service analytics."""
    if not fleet_ids.strip():
        return {"fleets": {}}

    from app.models.vehicle import Vehicle

    ids = [UUID(f.strip()) for f in fleet_ids.split(",") if f.strip()]
    fleet_repo = FleetRepository(session)

    result = {}
    for fid in ids:
        fleet = await fleet_repo.get_by_id(fid)
        if fleet:
            vehicle_count_result = await session.execute(
                select(func.count()).select_from(Vehicle).where(
                    Vehicle.business_id == fid,
                    Vehicle.deleted_at.is_(None),
                )
            )
            vehicle_count = vehicle_count_result.scalar_one()
            result[str(fid)] = {
                "name": fleet.name,
                "logo_url": fleet.logo_url,
                "vehicle_count": vehicle_count,
            }
    return {"fleets": result}


@router.get("/facilities/count")
async def get_facility_count(
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Count of users with FACILITY role. Called by ride-service analytics."""
    from app.models.user import User

    result = await session.execute(
        select(func.count()).select_from(User).where(
            User.role == "facility",
            User.is_active.is_(True),
        )
    )
    return {"count": result.scalar_one()}


@router.get("/facilities/top")
async def get_top_facilities(
    facility_ids: str = "",
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Batch get facility user details. Called by ride-service analytics."""
    if not facility_ids.strip():
        return {"facilities": {}}

    from app.models.user import User

    ids = [UUID(f.strip()) for f in facility_ids.split(",") if f.strip()]
    result = {}
    for fid in ids:
        user_result = await session.execute(
            select(User).where(User.id == fid)
        )
        user = user_result.scalar_one_or_none()
        if user:
            result[str(fid)] = {
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown Facility",
                "facility_type": None,
                "email": user.email,
                "phone": user.phone,
                "avatar_url": user.avatar_url,
            }
    return {"facilities": result}


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


@router.get("/admin-invitations/verify")
async def verify_admin_invitation(
    token: str,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Verify an admin invitation token. Called by auth-service."""
    from app.repositories.admin_invitation_repo import AdminInvitationRepository
    from app.repositories.admin_role_repo import AdminRoleRepository

    invitation_repo = AdminInvitationRepository(session)
    role_repo = AdminRoleRepository(session)

    invitation = await invitation_repo.get_by_token(token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Invitation already used or revoked")

    if invitation.expires_at < utc_now():
        raise HTTPException(status_code=400, detail="Invitation has expired")

    role = await role_repo.get_by_name(invitation.role_name)
    role_display_name = role.display_name if role else invitation.role_name

    return {
        "valid": True,
        "email": invitation.email,
        "full_name": invitation.full_name,
        "role_name": invitation.role_name,
        "role_display_name": role_display_name,
        "invitation_id": str(invitation.id),
    }


@router.post("/admin-invitations/accept")
async def accept_admin_invitation(
    request: AcceptInvitationRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Mark an admin invitation as accepted and create admin role assignment. Called by auth-service after admin registration."""
    from app.repositories.admin_invitation_repo import AdminInvitationRepository
    from app.repositories.admin_role_repo import AdminRoleRepository
    from app.models.admin_role import AdminRoleAssignment

    invitation_repo = AdminInvitationRepository(session)
    role_repo = AdminRoleRepository(session)

    invitation = await invitation_repo.get_by_token(request.token)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")

    # Get the role
    role = await role_repo.get_by_name(invitation.role_name)
    if not role:
        raise HTTPException(status_code=400, detail="Admin role not found")

    # Create role assignment
    assignment = AdminRoleAssignment(
        user_id=UUID(request.user_id),
        role_id=role.id,
        assigned_by=invitation.invited_by,
    )
    await role_repo.assign_role(assignment)

    # Mark invitation as accepted
    await invitation_repo.mark_accepted(invitation.id)
    logger.info(
        f"Admin invitation {invitation.id} accepted by user {request.user_id}"
    )

    return {"accepted": True, "invitation_id": str(invitation.id)}


class CheckModuleAccessRequest(BaseModel):
    user_id: str
    module_name: str


@router.post("/check-module-access")
async def check_module_access(
    request: CheckModuleAccessRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Check if user has access to a module. Called by other services for permission enforcement."""
    from app.repositories.admin_role_repo import AdminRoleRepository
    from app.services.admin_role_service import AdminRoleService
    from app.repositories.user_repo import UserRepository

    role_service = AdminRoleService(
        role_repo=AdminRoleRepository(session),
        user_repo=UserRepository(session),
    )

    try:
        user_id = UUID(request.user_id)
        has_access = await role_service.check_module_access(user_id, request.module_name)
        return {"has_access": has_access}
    except ValueError:
        return {"has_access": False}
    except Exception as e:
        logger.error(f"Error checking module access: {e}")
        return {"has_access": False}
