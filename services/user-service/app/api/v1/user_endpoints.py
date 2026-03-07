from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
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
from mediride_common.exceptions import AuthorizationError
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_user_service(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(UserRepository(session))


@router.get("/me", response_model=StandardResponse[UserProfileResponse])
async def get_my_profile(
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    profile = await service.get_profile(user.id)
    return StandardResponse(data=UserProfileResponse.model_validate(profile))


@router.put("/me", response_model=StandardResponse[UserProfileResponse])
async def update_my_profile(
    request: UpdateProfileRequest,
    user: UserClaims = Depends(get_current_user),
    service: UserService = Depends(_get_user_service),
):
    update_data = request.model_dump(exclude_unset=True)
    profile = await service.update_profile(user.id, **update_data)
    return StandardResponse(
        data=UserProfileResponse.model_validate(profile),
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
