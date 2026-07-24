"""Internal API endpoints for inter-service communication.

These endpoints are NOT exposed through the API gateway.
They are called directly by other services within the Docker network.
"""
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.user_credential import UserCredential
from app.normalization import normalize_email, normalize_phone
from app.repositories.credential_repo import CredentialRepository
from app.schemas.activity_log import CreateActivityLogRequest
from app.services.activity_log_service import ActivityLogService
from app.services.password_service import hash_password, validate_password_strength
from mediride_common.schemas.enums import UserRole

# Reactivation tokens are self-contained signed JWTs (no DB storage needed).
REACTIVATION_TOKEN_EXPIRE_DAYS = 7

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal")


def _require_internal_service(
    x_internal_service: str | None = Header(None),
) -> str:
    if not x_internal_service:
        raise HTTPException(status_code=403, detail="Internal access only")
    return x_internal_service


def _mint_reactivation_token(user_id: UUID) -> str:
    """Create a signed, self-contained reactivation JWT for the emailed link."""
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": "reactivation",
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(days=REACTIVATION_TOKEN_EXPIRE_DAYS)).timestamp()
            ),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


class CreateDriverCredentialRequest(BaseModel):
    email: EmailStr
    phone: str | None = None
    password: str
    business_id: UUID


class CreateAdminCredentialRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/drivers/create-credential")
async def create_driver_credential(
    request: CreateDriverCredentialRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Create a driver credential. Called by user-service admin driver creation."""
    repo = CredentialRepository(session)
    normalized_email = normalize_email(str(request.email))
    normalized_phone = normalize_phone(request.phone)

    existing = await repo.get_by_email_or_phone(normalized_email, normalized_phone)
    if existing:
        if existing.email and normalized_email and existing.email.lower() == normalized_email:
            raise HTTPException(status_code=409, detail="Account with this email already exists")
        raise HTTPException(status_code=409, detail="Account with this phone number already exists")

    validate_password_strength(request.password)

    credential = UserCredential(
        email=normalized_email,
        phone=normalized_phone,
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


@router.post("/admins/create-credential")
async def create_admin_credential(
    request: CreateAdminCredentialRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Create an admin credential. Called by user-service admin invitation flow."""
    repo = CredentialRepository(session)
    normalized_email = normalize_email(str(request.email))

    existing = await repo.get_by_email_or_phone(normalized_email, None)
    if existing:
        raise HTTPException(status_code=409, detail="Account with this email already exists")

    validate_password_strength(request.password)

    credential = UserCredential(
        email=normalized_email,
        password_hash=hash_password(request.password),
        role=UserRole.ADMIN,
        business_id=None,
        is_verified=True,
    )
    try:
        await repo.create(credential)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Account with this email already exists")

    logger.info(f"Admin credential created internally: {credential.id}")
    return {
        "user_id": str(credential.id),
        "email": credential.email,
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Delete a user auth credential. Called by user-service when a driver is removed."""
    repo = CredentialRepository(session)
    credential = await repo.get_by_id(user_id)
    if not credential:
        raise HTTPException(status_code=404, detail="User not found")

    await repo.delete(user_id)

    logger.info(f"User credential deleted internally: {user_id}")
    return {"deleted": True, "user_id": str(user_id)}


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
    # A reactivated account is always verified so login is never left blocked.
    credential.is_verified = True
    credential.locked_until = None
    credential.failed_attempts = 0
    await session.flush()

    logger.info(f"User reactivated internally: {user_id}")
    return {"reactivated": True, "user_id": str(user_id)}


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr


@router.put("/users/{user_id}/change-email")
async def change_user_email(
    user_id: UUID,
    request: ChangeEmailRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Change a user's login email and deactivate the account pending reactivation.

    Called by user-service when an admin edits a driver's email. Returns a signed
    reactivation token; the driver re-activates via a link emailed to the new address.
    """
    repo = CredentialRepository(session)
    credential = await repo.get_by_id(user_id)
    if not credential:
        raise HTTPException(status_code=404, detail="User not found")

    normalized_email = normalize_email(str(request.new_email))

    # Reject if the new email already belongs to a different credential.
    existing = await repo.get_by_email_or_phone(normalized_email, None)
    if existing and existing.id != credential.id:
        raise HTTPException(status_code=409, detail="Email already in use")

    credential.email = normalized_email
    credential.is_active = False
    await session.flush()

    reactivation_token = _mint_reactivation_token(user_id)

    logger.info(f"User email changed + deactivated pending reactivation: {user_id}")
    return {"reactivation_token": reactivation_token, "user_id": str(user_id)}


@router.get("/users/{user_id}/reactivation-status")
async def get_reactivation_status(
    user_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Return whether the credential is currently active.

    user-service uses this to decide if a driver is still pending reactivation
    after an email change (is_active is False until the driver clicks the link).
    """
    repo = CredentialRepository(session)
    credential = await repo.get_by_id(user_id)
    if not credential:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": str(user_id), "is_active": credential.is_active}


@router.post("/users/{user_id}/resend-reactivation")
async def resend_reactivation(
    user_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Mint a fresh reactivation token for a driver still pending reactivation.

    Rejects with 409 if the account is already active (nothing to resend).
    """
    repo = CredentialRepository(session)
    credential = await repo.get_by_id(user_id)
    if not credential:
        raise HTTPException(status_code=404, detail="User not found")
    if credential.is_active:
        raise HTTPException(status_code=409, detail="Account is already active")

    reactivation_token = _mint_reactivation_token(user_id)
    logger.info(f"Reactivation email resend requested for {user_id}")
    return {
        "reactivation_token": reactivation_token,
        "user_id": str(user_id),
        "email": credential.email,
    }


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
