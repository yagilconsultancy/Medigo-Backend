import logging
from datetime import timedelta
from uuid import UUID

from app.config import settings
from app.models.refresh_token import RefreshToken
from app.models.user_credential import UserCredential
from app.repositories.credential_repo import CredentialRepository
from app.repositories.token_repo import TokenRepository
from app.services.otp_service import OTPService
from app.services.password_service import (
    hash_password,
    hash_token,
    validate_password_strength,
    verify_password,
)
from mediride_common.auth.jwt_handler import JWTHandler
from mediride_common.auth.models import TokenPair
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.events.schemas import UserRegisteredPayload, UserVerifiedPayload
from mediride_common.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from mediride_common.schemas.enums import UserRole
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        credential_repo: CredentialRepository,
        token_repo: TokenRepository,
        otp_service: OTPService,
        jwt_handler: JWTHandler,
        publisher: EventPublisher,
    ):
        self.credential_repo = credential_repo
        self.token_repo = token_repo
        self.otp_service = otp_service
        self.jwt_handler = jwt_handler
        self.publisher = publisher

    async def register(
        self,
        email: str | None,
        phone: str | None,
        password: str,
        role: UserRole,
        business_id: UUID | None = None,
    ) -> tuple[UUID, str]:
        """Register a new user. Returns (user_id, otp_code)."""
        validate_password_strength(password)

        # Check if user already exists
        existing = await self.credential_repo.get_by_email_or_phone(email, phone)
        if existing:
            raise ConflictError("An account with this email or phone already exists")

        # Create credential
        credential = UserCredential(
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            role=role,
            business_id=business_id,
            is_verified=False,
        )
        await self.credential_repo.create(credential)

        # Generate OTP
        channel = "email" if email else "sms"
        otp_code = await self.otp_service.generate_otp(
            credential.id, "registration", channel
        )

        # Publish event
        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.USER_REGISTERED,
            UserRegisteredPayload(
                user_id=credential.id,
                email=email,
                phone=phone,
                role=role,
                business_id=business_id,
            ).model_dump(mode="json"),
        )

        logger.info(f"User registered: {credential.id}, role={role}")
        return credential.id, otp_code

    async def verify_otp(self, user_id: UUID, code: str, purpose: str) -> bool:
        """Verify OTP and mark user as verified."""
        credential = await self.credential_repo.get_by_id(user_id)
        if not credential:
            raise NotFoundError("User not found")

        await self.otp_service.verify_otp(user_id, code, purpose)

        if purpose == "registration":
            await self.credential_repo.update_verified(user_id, True)

            # Publish verified event
            await self.publisher.publish(
                Exchanges.AUTH,
                RoutingKeys.USER_VERIFIED,
                UserVerifiedPayload(
                    user_id=user_id,
                    email=credential.email,
                    phone=credential.phone,
                ).model_dump(mode="json"),
            )

        return True

    async def login(
        self, email: str | None, phone: str | None, password: str
    ) -> TokenPair:
        """Authenticate user and return token pair."""
        credential = await self.credential_repo.get_by_email_or_phone(email, phone)
        if not credential:
            raise AuthenticationError("Invalid credentials")

        # Check if account is locked
        if credential.locked_until and credential.locked_until > utc_now():
            raise AuthenticationError(
                "Account is temporarily locked. Please try again later."
            )

        # Check if account is active
        if not credential.is_active:
            raise AuthenticationError("Account is deactivated")

        # Verify password
        if not verify_password(password, credential.password_hash):
            await self.credential_repo.increment_failed_attempts(credential.id)

            # Lock after max attempts
            if credential.failed_attempts + 1 >= settings.MAX_LOGIN_ATTEMPTS:
                locked_until = utc_now() + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
                await self.credential_repo.lock_account(credential.id, locked_until)

            raise AuthenticationError("Invalid credentials")

        # Check if verified
        if not credential.is_verified:
            raise AuthenticationError("Account not verified. Please verify your OTP.")

        # Reset failed attempts
        await self.credential_repo.reset_failed_attempts(credential.id)

        # Create tokens
        token_pair = self.jwt_handler.create_token_pair(
            user_id=str(credential.id),
            role=credential.role,
            business_id=str(credential.business_id) if credential.business_id else None,
            email=credential.email,
        )

        # Store refresh token
        refresh_token_record = RefreshToken(
            user_id=credential.id,
            token_hash=hash_token(token_pair.refresh_token),
            expires_at=utc_now()
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.token_repo.create(refresh_token_record)

        return token_pair

    async def refresh_token(self, refresh_token: str) -> TokenPair:
        """Refresh access token using refresh token."""
        # Decode refresh token to get user ID
        payload = self.jwt_handler.decode_token(refresh_token)
        if payload.type != "refresh":
            raise AuthenticationError("Invalid token type")

        # Verify token exists and is not revoked
        token_hash = hash_token(refresh_token)
        stored_token = await self.token_repo.get_by_hash(token_hash)
        if not stored_token:
            raise AuthenticationError("Invalid or revoked refresh token")

        # Check expiry
        if stored_token.expires_at < utc_now():
            raise AuthenticationError("Refresh token expired")

        # Revoke old refresh token (rotation)
        await self.token_repo.revoke(stored_token.id)

        # Get user
        credential = await self.credential_repo.get_by_id(stored_token.user_id)
        if not credential or not credential.is_active:
            raise AuthenticationError("Account not found or deactivated")

        # Create new token pair
        new_token_pair = self.jwt_handler.create_token_pair(
            user_id=str(credential.id),
            role=credential.role,
            business_id=str(credential.business_id) if credential.business_id else None,
            email=credential.email,
        )

        # Store new refresh token
        new_refresh_record = RefreshToken(
            user_id=credential.id,
            token_hash=hash_token(new_token_pair.refresh_token),
            expires_at=utc_now()
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.token_repo.create(new_refresh_record)

        return new_token_pair

    async def logout(self, user_id: UUID, refresh_token: str) -> None:
        """Revoke a specific refresh token."""
        token_hash = hash_token(refresh_token)
        stored_token = await self.token_repo.get_by_hash(token_hash)
        if stored_token and stored_token.user_id == user_id:
            await self.token_repo.revoke(stored_token.id)

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> None:
        """Change user password."""
        validate_password_strength(new_password)

        credential = await self.credential_repo.get_by_id(user_id)
        if not credential:
            raise NotFoundError("User not found")

        if not verify_password(current_password, credential.password_hash):
            raise AuthenticationError("Current password is incorrect")

        await self.credential_repo.update_password(
            user_id, hash_password(new_password)
        )

        # Revoke all refresh tokens (force re-login)
        await self.token_repo.revoke_all_for_user(user_id)

    async def resend_otp(self, user_id: UUID, purpose: str) -> str:
        """Resend OTP for a user."""
        credential = await self.credential_repo.get_by_id(user_id)
        if not credential:
            raise NotFoundError("User not found")

        channel = "email" if credential.email else "sms"
        return await self.otp_service.generate_otp(user_id, purpose, channel)
