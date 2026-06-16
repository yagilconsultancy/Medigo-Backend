from datetime import date
from uuid import UUID as PyUUID
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.auth_service_client import AuthServiceClient
from app.config import settings
from app.dependencies import get_db, get_s3_client
from app.repositories.user_repo import UserRepository
from app.repositories.emergency_contact_repo import EmergencyContactRepository
from app.models.emergency_contact import EmergencyContact
from app.schemas.user import (
    ConsentResponse,
    EmergencyContactCreate,
    EmergencyContactResponse,
    OnboardingStatusResponse,
    UpdateConsentRequest,
    UpdateProfileRequest,
    UserProfileResponse,
)
from app.services.user_service import UserService
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import AuthorizationError, ValidationError
from mediride_common.schemas.responses import StandardResponse
from mediride_common.storage.s3_client import S3StorageClient

router = APIRouter()


def _get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(UserRepository(session))


def _get_user_service_with_auth(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(
        UserRepository(session),
        auth_client=AuthServiceClient(settings.AUTH_SERVICE_URL),
    )


@router.get("/me", response_model=StandardResponse[UserProfileResponse])
async def get_my_profile(
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    profile = await service.get_profile(user.id)
    data = UserProfileResponse.model_validate(profile)
    if data.avatar_url and data.avatar_url.startswith("s3://"):
        path = data.avatar_url[len("s3://"):]
        bucket, _, key = path.partition("/")
        data.avatar_url = await s3_client.generate_presigned_url(bucket, key)
    return StandardResponse(data=data)


@router.put("/me", response_model=StandardResponse[UserProfileResponse])
async def update_my_profile(
    first_name: str | None = Form(None),
    last_name: str | None = Form(None),
    date_of_birth: str | None = Form(None),
    gender: str | None = Form(None),
    home_address: str | None = Form(None),
    medical_notes: str | None = Form(None),
    avatar: UploadFile | None = File(None),
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    """
    Update user profile with form data (supports avatar upload).

    Send as multipart/form-data. All fields optional.
    Avatar: JPEG, PNG, WebP, or GIF (max 5MB).

    For JSON-only updates (no file), use PATCH /me instead.
    """
    update_data = {}

    # Collect form data fields
    if first_name is not None:
        update_data["first_name"] = first_name
    if last_name is not None:
        update_data["last_name"] = last_name
    if date_of_birth is not None:
        try:
            update_data["date_of_birth"] = date.fromisoformat(date_of_birth)
        except ValueError:
            raise ValidationError("date_of_birth must be in YYYY-MM-DD format")
    if gender is not None:
        update_data["gender"] = gender
    if home_address is not None:
        update_data["home_address"] = home_address
    if medical_notes is not None:
        update_data["medical_notes"] = medical_notes

    # Handle avatar upload
    if avatar and avatar.filename:
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"]
        if avatar.content_type not in allowed_types:
            raise ValidationError(
                f"Invalid file type. Allowed: JPEG, PNG, WebP, GIF"
            )

        file_data = await avatar.read()
        if len(file_data) > 5 * 1024 * 1024:
            raise ValidationError("File size must be less than 5MB")

        # Generate unique file key
        file_extension = avatar.filename.split(".")[-1] if "." in avatar.filename else "jpg"
        file_key = f"avatars/{user.id}/{uuid.uuid4()}.{file_extension}"

        # Upload to S3
        await s3_client.ensure_bucket_exists(settings.S3_BUCKET_DOCUMENTS)
        await s3_client.upload_file(
            bucket=settings.S3_BUCKET_DOCUMENTS,
            key=file_key,
            file_data=file_data,
            content_type=avatar.content_type,
        )

        update_data["avatar_url"] = f"s3://{settings.S3_BUCKET_DOCUMENTS}/{file_key}"

    if not update_data:
        raise ValidationError("No fields provided for update")

    profile = await service.update_profile(user.id, **update_data)
    data = UserProfileResponse.model_validate(profile)
    if data.avatar_url and data.avatar_url.startswith("s3://"):
        path = data.avatar_url[len("s3://"):]
        bucket, _, key = path.partition("/")
        data.avatar_url = await s3_client.generate_presigned_url(bucket, key)
    return StandardResponse(
        data=data,
        message="Profile updated",
    )


@router.patch("/me", response_model=StandardResponse[UserProfileResponse])
async def update_my_profile_json(
    request: UpdateProfileRequest,
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    """
    Update user profile with JSON (no file upload).

    Send as application/json with only the fields you want to update.
    For avatar upload, use PUT /me with multipart/form-data instead.
    """
    update_data = request.model_dump(exclude_unset=True)
    profile = await service.update_profile(user.id, **update_data)
    data = UserProfileResponse.model_validate(profile)
    if data.avatar_url and data.avatar_url.startswith("s3://"):
        path = data.avatar_url[len("s3://"):]
        bucket, _, key = path.partition("/")
        data.avatar_url = await s3_client.generate_presigned_url(bucket, key)
    return StandardResponse(
        data=data,
        message="Profile updated",
    )


# Emergency Contacts
@router.get(
    "/me/emergency-contacts",
    response_model=StandardResponse[list[EmergencyContactResponse]],
)
async def list_emergency_contacts(
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = EmergencyContactRepository(session)
    contacts = await repo.list_by_user(user.id)
    return StandardResponse(
        data=[EmergencyContactResponse.model_validate(c) for c in contacts]
    )


@router.post(
    "/me/emergency-contacts",
    response_model=StandardResponse[EmergencyContactResponse],
)
async def create_emergency_contact(
    request: EmergencyContactCreate,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = EmergencyContactRepository(session)
    contact = EmergencyContact(
        user_id=user.id,
        name=request.name,
        phone=request.phone,
        relationship_type=request.relationship_type,
        is_primary=request.is_primary,
    )
    await repo.create(contact)
    return StandardResponse(
        data=EmergencyContactResponse.model_validate(contact),
        message="Emergency contact added",
    )


@router.delete("/me/emergency-contacts/{contact_id}", response_model=StandardResponse)
async def delete_emergency_contact(
    contact_id: str,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from uuid import UUID

    repo = EmergencyContactRepository(session)
    contact = await repo.get_by_id(UUID(contact_id))
    if not contact or contact.user_id != user.id:
        raise AuthorizationError("Contact not found or access denied")
    await repo.delete(UUID(contact_id))
    return StandardResponse(message="Emergency contact deleted")


# Consent Management
@router.get("/me/consent", response_model=StandardResponse[ConsentResponse])
async def get_my_consent(
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    """Get current consent/agreement status."""
    profile = await service.get_profile(user.id)
    return StandardResponse(data=ConsentResponse.model_validate(profile))


@router.put("/me/consent", response_model=StandardResponse[ConsentResponse])
async def update_my_consent(
    request: UpdateConsentRequest,
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    """Accept or update consent agreements (911 Emergency, Privacy Policy, Terms of Service, Data & Location)."""
    profile = await service.update_consent(
        user.id,
        consent_emergency_services=request.consent_emergency_services,
        consent_privacy_policy=request.consent_privacy_policy,
        consent_terms_of_service=request.consent_terms_of_service,
        consent_data_location=request.consent_data_location,
    )
    return StandardResponse(
        data=ConsentResponse.model_validate(profile),
        message="Consent updated",
    )


# Onboarding Progress
@router.get("/me/onboarding", response_model=StandardResponse[OnboardingStatusResponse])
async def get_onboarding_status(
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    """Get onboarding progress (step tracking)."""
    profile = await service.get_profile(user.id)
    status = service.get_onboarding_status(profile)
    return StandardResponse(data=OnboardingStatusResponse(**status))


@router.put("/me/onboarding/{step}", response_model=StandardResponse[OnboardingStatusResponse])
async def advance_onboarding(
    step: int,
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    """Mark an onboarding step as reached (steps 1-5)."""
    if step < 1 or step > 6:
        from mediride_common.exceptions import ValidationError
        raise ValidationError("Step must be between 1 and 6")
    profile = await service.update_onboarding_step(user.id, step)
    status = service.get_onboarding_status(profile)
    return StandardResponse(
        data=OnboardingStatusResponse(**status),
        message="Onboarding progress updated",
    )


# Account Deletion
@router.delete("/me", response_model=StandardResponse)
async def delete_my_account(
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service_with_auth),
):
    """Permanently delete the current user's account (soft-delete)."""
    await service.delete_account(user.id)
    return StandardResponse(message="Account deleted successfully")
