"""Internal API endpoints for inter-service communication.

These endpoints are NOT exposed through the API gateway.
They are called directly by other services within the Docker network.
"""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.user_credential import UserCredential
from app.repositories.credential_repo import CredentialRepository
from app.schemas.activity_log import CreateActivityLogRequest
from app.services.activity_log_service import ActivityLogService
from app.services.password_service import hash_password, validate_password_strength
from mediride_common.schemas.enums import UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal")


def _require_internal_service(
    x_internal_service: str | None = Header(None),
) -> str:
    if not x_internal_service:
        raise HTTPException(status_code=403, detail="Internal access only")
    return x_internal_service


class CreateDriverCredentialRequest(BaseModel):
    email: EmailStr
    phone: str | None = None
    password: str
    business_id: UUID


@router.post("/drivers/create-credential")
async def create_driver_credential(
    request: CreateDriverCredentialRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Create a driver credential. Called by user-service admin driver creation."""
    repo = CredentialRepository(session)

    existing = await repo.get_by_email_or_phone(request.email, request.phone)
    if existing:
        if existing.email == request.email:
            raise HTTPException(status_code=409, detail="Account with this email already exists")
        raise HTTPException(status_code=409, detail="Account with this phone number already exists")

    validate_password_strength(request.password)

    credential = UserCredential(
        email=request.email,
        phone=request.phone,
        password_hash=hash_password(request.password),
        role=UserRole.DRIVER,
        business_id=request.business_id,
        is_verified=True,
    )
    try:
        await repo.create(credential)
    except IntegrityError as e:
        error_str = str(e.orig) if e.orig else str(e)
        if "ix_user_credentials_phone" in error_str or "phone" in error_str:
            raise HTTPException(status_code=409, detail="Account with this phone number already exists")
        if "ix_user_credentials_email" in error_str or "email" in error_str:
            raise HTTPException(status_code=409, detail="Account with this email already exists")
        raise HTTPException(status_code=409, detail="Account with this email or phone already exists")

    logger.info(f"Driver credential created internally: {credential.id}")
    return {
        "user_id": str(credential.id),
        "email": credential.email,
    }


@router.put("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Deactivate a user account. Called by user-service on driver suspension/deactivation."""
    repo = CredentialRepository(session)
    credential = await repo.get_by_id(user_id)
    if not credential:
        raise HTTPException(status_code=404, detail="User not found")

    credential.is_active = False
    await session.flush()

    logger.info(f"User deactivated internally: {user_id}")
    return {"deactivated": True, "user_id": str(user_id)}


@router.put("/users/{user_id}/reactivate")
async def reactivate_user(
    user_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Reactivate a user account. Called by user-service on driver reactivation."""
    repo = CredentialRepository(session)
    credential = await repo.get_by_id(user_id)
    if not credential:
        raise HTTPException(status_code=404, detail="User not found")

    credential.is_active = True
    credential.locked_until = None
    credential.failed_attempts = 0
    await session.flush()

    logger.info(f"User reactivated internally: {user_id}")
    return {"reactivated": True, "user_id": str(user_id)}


@router.post("/activity-logs")
async def create_activity_log(
    request: CreateActivityLogRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Create an activity log entry. Called by other services to record admin actions."""
    service = ActivityLogService(session)
    log = await service.create_log(
        admin_id=request.admin_id,
        admin_name=request.admin_name,
        admin_email=request.admin_email,
        action_title=request.action_title,
        action_description=request.action_description,
        category=request.category,
        severity=request.severity,
        target_entity_id=request.target_entity_id,
        target_entity_type=request.target_entity_type,
    )
    logger.info(f"Activity log created internally: {log.id}")
    return {"id": str(log.id), "log_number": log.log_number}
