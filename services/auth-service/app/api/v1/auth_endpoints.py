from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.dependencies import get_db, get_publisher
from app.repositories.credential_repo import CredentialRepository
from app.repositories.otp_repo import OTPRepository
from app.repositories.token_repo import TokenRepository
from app.schemas.auth import (
    AdminRegisterRequest,
    AdminVerifyInviteRequest,
    ChangePasswordRequest,
    DriverRegisterRequest,
    DriverVerifyInviteRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    InviteVerifyResponse,
    LoginRequest,
    OTPVerifyResponse,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    VerifyOTPRequest,
)
from app.services.auth_service import AuthService
from mediride_common.auth.models import TokenPair
from app.services.login_history_service import LoginHistoryService
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
    otp_service = OTPService(otp_repo)
    jwt_handler = JWTHandler(
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        access_token_expire_minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    )
    user_service_client = UserServiceClient(settings.USER_SERVICE_URL)
    login_history_service = LoginHistoryService(session)
    return AuthService(
        credential_repo=credential_repo,
        token_repo=token_repo,
        otp_service=otp_service,
        jwt_handler=jwt_handler,
        publisher=publisher,
        user_service_client=user_service_client,
        login_history_service=login_history_service,
    )


@router.post("/register", response_model=StandardResponse[RegisterResponse])
async def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    user_id, _ = await auth_service.register(
        email=request.email,
        phone=request.phone,
        password=request.password,
        role=request.role,
        first_name=request.first_name,
        last_name=request.last_name,
    )
    message = "Registration successful. Please verify your account."

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
            role=token_pair.role,
        ),
        message="Login successful",
    )


@router.post("/admin/login", response_model=StandardResponse[TokenResponse])
async def admin_login(
    request: LoginRequest,
    raw_request: Request,
    auth_service: AuthService = Depends(_get_auth_service),
):
    ip_address = raw_request.headers.get("x-forwarded-for", raw_request.client.host if raw_request.client else "unknown")
    user_agent = raw_request.headers.get("user-agent", "")
    token_pair = await auth_service.admin_login(
        email=request.email,
        phone=request.phone,
        password=request.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return StandardResponse(
        data=TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            expires_in=token_pair.expires_in,
            role=token_pair.role,
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
            role=token_pair.role,
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
    await auth_service.resend_otp(user_id, purpose)
    return StandardResponse(message="OTP sent successfully")


@router.post("/forgot-password", response_model=StandardResponse[ForgotPasswordResponse])
async def forgot_password(
    request: ForgotPasswordRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    result = await auth_service.forgot_password(
        email=request.email, phone=request.phone
    )
    message = "If an account exists, a password reset OTP has been sent."
    if result:
        user_id, _ = result
        return StandardResponse(
            data=ForgotPasswordResponse(user_id=user_id, message=message),
            message=message,
        )
    return StandardResponse(message=message)


@router.post("/reset-password", response_model=StandardResponse)
async def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    await auth_service.reset_password(
        user_id=request.user_id,
        code=request.code,
        new_password=request.new_password,
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
            fleet_name=result.get("fleet_name"),
            email=result.get("email"),
        ),
        message="Invitation is valid",
    )


@router.post(
    "/driver/register",
)
async def register_driver(
    request: DriverRegisterRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    result = await auth_service.register_driver(
        invite_token=request.invite_token,
        password=request.password,
    )

    # If credential was pre-created by admin, result is a TokenPair (login)
    if isinstance(result, TokenPair):
        return StandardResponse(
            data=TokenResponse(
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                token_type=result.token_type,
                expires_in=result.expires_in,
                role=result.role,
            ),
            message="Login successful",
        )

    # Otherwise it's a new registration (user_id, otp_code)
    user_id, _ = result
    message = "Driver registration successful. Please verify your account."

    return StandardResponse(
        data=RegisterResponse(user_id=user_id, message=message),
        message=message,
    )


@router.post(
    "/admin/verify-invite",
    response_model=StandardResponse[InviteVerifyResponse],
)
async def verify_admin_invite(
    request: AdminVerifyInviteRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    result = await auth_service.verify_admin_invite(request.invite_token)
    return StandardResponse(
        data=InviteVerifyResponse(
            valid=True,
            fleet_name=result.get("role_display_name"),  # Reuse fleet_name field for role display
            email=result.get("email"),
        ),
        message="Invitation is valid",
    )


@router.post(
    "/admin/register",
    response_model=StandardResponse[TokenResponse],
)
async def register_admin(
    request: AdminRegisterRequest,
    auth_service: AuthService = Depends(_get_auth_service),
):
    token_pair = await auth_service.register_admin(
        invite_token=request.invite_token,
        password=request.password,
    )

    return StandardResponse(
        data=TokenResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type=token_pair.token_type,
            expires_in=token_pair.expires_in,
            role=token_pair.role,
        ),
        message="Admin registration successful. You are now logged in.",
    )
