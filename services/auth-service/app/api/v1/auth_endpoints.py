from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.credential_repo import CredentialRepository
from app.repositories.otp_repo import OTPRepository
from app.repositories.password_reset_repo import PasswordResetRepository
from app.repositories.token_repo import TokenRepository
from app.schemas.auth import (
    ChangePasswordRequest,
    DriverRegisterRequest,
    DriverVerifyInviteRequest,
    ForgotPasswordRequest,
    InviteVerifyResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    VerifyOTPRequest,
    OTPVerifyResponse,
)
from app.services.auth_service import AuthService
from app.services.otp_service import OTPService
from mediride_common.auth.jwt_handler import JWTHandler
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_auth_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> AuthService:
    credential_repo = CredentialRepository(session)
    token_repo = TokenRepository(session)
    otp_repo = OTPRepository(session)
    password_reset_repo = PasswordResetRepository(session)
    otp_service = OTPService(otp_repo)
    jwt_handler = JWTHandler(
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        access_token_expire_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    )
    user_service_client = UserServiceClient(settings.USER_SERVICE_URL)
    return AuthService(
        credential_repo=credential_repo,
        token_repo=token_repo,
        otp_service=otp_service,
        jwt_handler=jwt_handler,
        publisher=publisher,
        password_reset_repo=password_reset_repo,
        user_service_client=user_service_client,
    )


@router.post("/register", response_model=StandardResponse[RegisterResponse])
async def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    user_id, otp_code = await auth_service.register(
        email=request.email,
        phone=request.phone,
        password=request.password,
        role=request.role,
    )
    # In production, OTP is sent via notification service (email/SMS)
    # In development, we return it in the response for testing
    message = "Registration successful. Please verify your account."
    if settings.ENVIRONMENT != "production":
        message += f" [DEV] OTP: {otp_code}"

    return StandardResponse(
        data=RegisterResponse(user_id=user_id, message=message),
        message=message,
    )


@router.post("/verify-otp", response_model=StandardResponse[OTPVerifyResponse])
async def verify_otp(
    request: VerifyOTPRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    await auth_service.verify_otp(
        user_id=request.user_id,
        code=request.code,
        purpose=request.purpose,
    )
    return StandardResponse(
        data=OTPVerifyResponse(),
        message="Account verified successfully",
    )


@router.post("/login", response_model=StandardResponse[TokenResponse])
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    token_pair = await auth_service.login(
        email=request.email,
        phone=request.phone,
        password=request.password,
    )
    return StandardResponse(
        data=TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
        ),
        message="Login successful",
    )


@router.post("/admin/login", response_model=StandardResponse[TokenResponse])
async def admin_login(
    request: LoginRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    token_pair = await auth_service.admin_login(
        email=request.email,
        phone=request.phone,
        password=request.password,
    )
    return StandardResponse(
        data=TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
        ),
        message="Admin login successful",
    )


@router.post("/refresh", response_model=StandardResponse[TokenResponse])
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    token_pair = await auth_service.refresh_token(request.refresh_token)
    return StandardResponse(
        data=TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
        ),
        message="Token refreshed successfully",
    )


@router.post("/logout", response_model=StandardResponse)
async def logout(
    request: RefreshTokenRequest,
    user: UserClaims = Depends(get_current_user),
    auth_service: AuthService = Depends(_get_auth_service),
):
    await auth_service.logout(user.id, request.refresh_token)
    return StandardResponse(message="Logged out successfully")


@router.post("/change-password", response_model=StandardResponse)
async def change_password(
    request: ChangePasswordRequest,
    user: UserClaims = Depends(get_current_user),
    auth_service: AuthService = Depends(_get_auth_service),
):
    await auth_service.change_password(
        user_id=user.id,
        current_password=request.current_password,
        new_password=request.new_password,
    )
    return StandardResponse(message="Password changed successfully")


@router.post("/resend-otp", response_model=StandardResponse)
async def resend_otp(
    user_id: UUID,
    purpose: str = "registration",
    auth_service: AuthService = Depends(_get_auth_service),
):
    otp_code = await auth_service.resend_otp(user_id, purpose)
    message = "OTP sent successfully"
    if settings.ENVIRONMENT != "production":
        message += f" [DEV] OTP: {otp_code}"
    return StandardResponse(message=message)


@router.post("/forgot-password", response_model=StandardResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    token = await auth_service.forgot_password(
        email=request.email, phone=request.phone
    )
    message = "If an account exists, a password reset link has been sent."
    if settings.ENVIRONMENT == "development" and token:
        message += f" [DEV] Token: {token}"
    return StandardResponse(message=message)


@router.post("/reset-password", response_model=StandardResponse)
async def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    await auth_service.reset_password(
        token=request.token, new_password=request.new_password
    )
    return StandardResponse(message="Password reset successfully. Please log in.")


@router.post(
    "/driver/verify-invite",
    response_model=StandardResponse[InviteVerifyResponse],
)
async def verify_driver_invite(
    request: DriverVerifyInviteRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    result = await auth_service.verify_driver_invite(request.invite_token)
    return StandardResponse(
        data=InviteVerifyResponse(
            valid=True,
            business_name=result.get("business_name"),
            email=result.get("email"),
        ),
        message="Invitation is valid",
    )


@router.post(
    "/driver/register",
    response_model=StandardResponse[RegisterResponse],
)
async def register_driver(
    request: DriverRegisterRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    user_id, otp_code = await auth_service.register_driver(
        invite_token=request.invite_token,
        password=request.password,
    )
    message = "Driver registration successful. Please verify your account."
    if settings.ENVIRONMENT != "production":
        message += f" [DEV] OTP: {otp_code}"

    return StandardResponse(
        data=RegisterResponse(user_id=user_id, message=message),
        message=message,
    )
