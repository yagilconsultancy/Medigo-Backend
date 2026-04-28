import logging
import secrets
from datetime import timedelta
from uuid import UUID

import httpx

from app.config import settings
from app.models.password_reset import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user_credential import UserCredential
from app.repositories.credential_repo import CredentialRepository
from app.repositories.password_reset_repo import PasswordResetRepository
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
from mediride_common.events.schemas import (
    PasswordResetRequestedPayload,
    UserRegisteredPayload,
    UserVerifiedPayload,
)
from mediride_common.exceptions import (
    AuthenticationError,
    ConflictError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from mediride_common.schemas.enums import UserRole
from mediride_common.utils import utc_now

logger = logging.getLogger(__name__)

PASSWORD_RESET_EXPIRE_MINUTES = 30


class AuthService:
    def __init__(
        self,
        credential_repo: CredentialRepository,
        token_repo: TokenRepository,
        otp_service: OTPService,
        jwt_handler: JWTHandler,
        publisher: EventPublisher,
        password_reset_repo: PasswordResetRepository | None = None,
        user_service_client=None,
        login_history_service=None,
    ):
        self.credential_repo = credential_repo
        self.token_repo = token_repo
        self.otp_service = otp_service
        self.jwt_handler = jwt_handler
        self.publisher = publisher
        self.password_reset_repo = password_reset_repo
        self.user_service_client = user_service_client
        self.login_history_service = login_history_service

    async def register(
        self,
        email: str | None,
        phone: str | None,
        password: str,
        role: UserRole,
        business_id: UUID | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
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
                first_name=first_name,
                last_name=last_name,
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
        token_pair.role = credential.role

        # Store refresh token
        refresh_token_record = RefreshToken(
            user_id=credential.id,
            token_hash=hash_token(token_pair.refresh_token),
            expires_at=utc_now()
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.token_repo.create(refresh_token_record)

        return token_pair

    async def admin_login(
        self,
        email: str | None,
        phone: str | None,
        password: str,
        ip_address: str = "unknown",
        user_agent: str = "",
    ) -> TokenPair:
        """Authenticate admin user. Rejects non-admin roles."""
        device_info = self._parse_device_info(user_agent)

        credential = await self.credential_repo.get_by_email_or_phone(email, phone)
        if not credential:
            await self._record_login(
                user_id=None,
                admin_name="Unknown",
                admin_email=email or "unknown",
                ip_address=ip_address,
                device_info=device_info,
                success=False,
                failure_reason="Invalid credentials",
            )
            raise AuthenticationError("Invalid credentials")

        admin_name = credential.email or "Admin"
        admin_email = credential.email or ""

        # Check if account is locked
        if credential.locked_until and credential.locked_until > utc_now():
            await self._record_login(
                user_id=credential.id,
                admin_name=admin_name,
                admin_email=admin_email,
                ip_address=ip_address,
                device_info=device_info,
                success=False,
                failure_reason="Account locked",
            )
            raise AuthenticationError(
                "Account is temporarily locked. Please try again later."
            )

        if not credential.is_active:
            await self._record_login(
                user_id=credential.id,
                admin_name=admin_name,
                admin_email=admin_email,
                ip_address=ip_address,
                device_info=device_info,
                success=False,
                failure_reason="Account deactivated",
            )
            raise AuthenticationError("Account is deactivated")

        # Verify password
        if not verify_password(password, credential.password_hash):
            await self.credential_repo.increment_failed_attempts(credential.id)
            if credential.failed_attempts + 1 >= settings.MAX_LOGIN_ATTEMPTS:
                locked_until = utc_now() + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
                await self.credential_repo.lock_account(credential.id, locked_until)
            await self._record_login(
                user_id=credential.id,
                admin_name=admin_name,
                admin_email=admin_email,
                ip_address=ip_address,
                device_info=device_info,
                success=False,
                failure_reason="Invalid password",
            )
            raise AuthenticationError("Invalid credentials")

        if not credential.is_verified:
            await self._record_login(
                user_id=credential.id,
                admin_name=admin_name,
                admin_email=admin_email,
                ip_address=ip_address,
                device_info=device_info,
                success=False,
                failure_reason="Account not verified",
            )
            raise AuthenticationError("Account not verified. Please verify your OTP.")

        # Admin-only check
        if credential.role != UserRole.ADMIN:
            await self._record_login(
                user_id=credential.id,
                admin_name=admin_name,
                admin_email=admin_email,
                ip_address=ip_address,
                device_info=device_info,
                success=False,
                failure_reason="Non-admin role",
            )
            raise AuthenticationError("Access denied. Admin credentials required.")

        # Reset failed attempts
        await self.credential_repo.reset_failed_attempts(credential.id)

        # Create tokens
        token_pair = self.jwt_handler.create_token_pair(
            user_id=str(credential.id),
            role=credential.role,
            business_id=str(credential.business_id) if credential.business_id else None,
            email=credential.email,
        )
        token_pair.role = credential.role

        # Store refresh token
        refresh_token_record = RefreshToken(
            user_id=credential.id,
            token_hash=hash_token(token_pair.refresh_token),
            expires_at=utc_now()
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.token_repo.create(refresh_token_record)

        # Record successful login
        await self._record_login(
            user_id=credential.id,
            admin_name=admin_name,
            admin_email=admin_email,
            ip_address=ip_address,
            device_info=device_info,
            success=True,
        )

        return token_pair

    async def _record_login(
        self,
        user_id,
        admin_name: str,
        admin_email: str,
        ip_address: str,
        device_info: str,
        success: bool,
        failure_reason: str | None = None,
    ) -> None:
        """Record admin login attempt if login_history_service is available."""
        if not self.login_history_service:
            return
        try:
            from uuid import uuid4

            uid = user_id or uuid4()
            await self.login_history_service.record_login(
                user_id=uid,
                admin_name=admin_name,
                admin_email=admin_email,
                ip_address=ip_address,
                device_info=device_info,
                success=success,
                failure_reason=failure_reason,
            )
        except Exception as e:
            logger.warning(f"Failed to record login attempt: {e}")

    @staticmethod
    def _parse_device_info(user_agent: str) -> str:
        """Parse user-agent into a readable device string."""
        if not user_agent:
            return "Unknown device"
        ua = user_agent.lower()
        browser = "Unknown"
        if "chrome" in ua and "edg" not in ua:
            browser = "Chrome"
        elif "firefox" in ua:
            browser = "Firefox"
        elif "safari" in ua and "chrome" not in ua:
            browser = "Safari"
        elif "edg" in ua:
            browser = "Edge"
        os_name = "Unknown"
        if "windows" in ua:
            os_name = "Windows"
        elif "macintosh" in ua or "mac os" in ua:
            os_name = "macOS"
        elif "linux" in ua:
            os_name = "Linux"
        elif "iphone" in ua or "ipad" in ua:
            os_name = "iOS"
        elif "android" in ua:
            os_name = "Android"
        return f"{browser} · {os_name}"

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
        new_token_pair.role = credential.role

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

    async def forgot_password(
        self, email: str | None, phone: str | None
    ) -> str | None:
        """Request a password reset. Returns token in dev mode."""
        credential = await self.credential_repo.get_by_email_or_phone(email, phone)
        if not credential:
            # Return silently to prevent user enumeration
            logger.info("Password reset requested for non-existent account")
            return None

        if not credential.is_active:
            return None

        # Invalidate any existing reset tokens
        await self.password_reset_repo.invalidate_all_for_user(credential.id)

        # Generate reset token
        raw_token = secrets.token_urlsafe(32)
        reset_record = PasswordResetToken(
            user_id=credential.id,
            token_hash=hash_token(raw_token),
            expires_at=utc_now() + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
        )
        await self.password_reset_repo.create(reset_record)

        # Publish event for notification
        if credential.email:
            await self.publisher.publish(
                Exchanges.AUTH,
                RoutingKeys.PASSWORD_RESET_REQUESTED,
                PasswordResetRequestedPayload(
                    user_id=credential.id,
                    email=credential.email,
                    reset_token=raw_token,
                ).model_dump(mode="json"),
            )

        logger.info(f"Password reset requested for user {credential.id}")
        return raw_token if settings.ENVIRONMENT != "production" else None

    async def reset_password(self, token: str, new_password: str) -> None:
        """Reset password using a valid reset token."""
        validate_password_strength(new_password)

        token_hash = hash_token(token)
        reset_record = await self.password_reset_repo.get_by_hash(token_hash)
        if not reset_record:
            raise AuthenticationError("Invalid or expired reset token")

        if reset_record.expires_at < utc_now():
            raise AuthenticationError("Reset token has expired")

        # Update password
        await self.credential_repo.update_password(
            reset_record.user_id, hash_password(new_password)
        )

        # Invalidate all reset tokens for this user
        await self.password_reset_repo.invalidate_all_for_user(reset_record.user_id)

        # Revoke all refresh tokens (force re-login)
        await self.token_repo.revoke_all_for_user(reset_record.user_id)

        logger.info(f"Password reset completed for user {reset_record.user_id}")

    async def verify_driver_invite(self, invite_token: str) -> dict:
        """Verify a driver invitation token via user-service."""
        if not self.user_service_client:
            raise ValidationError("Driver registration is not configured")

        result = await self.user_service_client.verify_invite_token(invite_token)
        return result

    async def register_driver(
        self, invite_token: str, password: str
    ) -> tuple[UUID, str] | TokenPair:
        """Register a driver using an invitation token.

        If the credential was already created by admin, verify password and
        return tokens (login flow) instead of creating a new account.
        """
        if not self.user_service_client:
            raise ValidationError("Driver registration is not configured")

        # Verify and get invite details
        invite_data = await self.user_service_client.verify_invite_token(invite_token)
        email = invite_data["email"]
        business_id = UUID(invite_data["business_id"])

        # Check if user already exists (admin-created driver)
        existing = await self.credential_repo.get_by_email_or_phone(email, None)
        if existing:
            # Credential was pre-created by admin — verify password and log in
            if not verify_password(password, existing.password_hash):
                raise AuthenticationError("Invalid credentials")

            # Accept the invitation in user-service
            await self.user_service_client.accept_invitation(
                invite_token, str(existing.id)
            )

            # Ensure account is verified
            if not existing.is_verified:
                await self.credential_repo.update_verified(existing.id, True)

            # Create tokens (login)
            token_pair = self.jwt_handler.create_token_pair(
                user_id=str(existing.id),
                role=existing.role,
                business_id=str(existing.business_id) if existing.business_id else None,
                email=existing.email,
            )
            token_pair.role = existing.role
            refresh_token_record = RefreshToken(
                user_id=existing.id,
                token_hash=hash_token(token_pair.refresh_token),
                expires_at=utc_now()
                + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            )
            await self.token_repo.create(refresh_token_record)

            logger.info(f"Admin-created driver logged in via register: {existing.id}")
            return token_pair

        validate_password_strength(password)

        # Create credential
        credential = UserCredential(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.DRIVER,
            business_id=business_id,
            is_verified=False,
        )
        await self.credential_repo.create(credential)

        # Generate OTP
        otp_code = await self.otp_service.generate_otp(
            credential.id, "registration", "email"
        )

        # Accept the invitation in user-service
        await self.user_service_client.accept_invitation(
            invite_token, str(credential.id)
        )

        # Publish registration event
        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.USER_REGISTERED,
            UserRegisteredPayload(
                user_id=credential.id,
                email=email,
                phone=None,
                role=UserRole.DRIVER,
                business_id=business_id,
            ).model_dump(mode="json"),
        )

        logger.info(
            f"Driver registered: {credential.id}, business={business_id}"
        )
        return credential.id, otp_code

    async def verify_admin_invite(self, invite_token: str) -> dict:
        """Verify an admin invitation token via user-service."""
        if not self.user_service_client:
            raise ValidationError("Admin registration is not configured")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.user_service_client._base_url}/internal/admin-invitations/verify",
                    params={"token": invite_token},
                    headers={"X-Internal-Service": "auth-service"},
                )
        except httpx.ConnectError:
            raise ValidationError("User service is unavailable")
        except httpx.TimeoutException:
            raise ValidationError("User service request timed out")

        if response.status_code == 404:
            raise NotFoundError("Invalid or expired invitation token")
        if response.status_code == 400:
            raise ValidationError(response.json().get("detail", "Invalid invitation"))
        if response.status_code != 200:
            raise ValidationError("Failed to verify invitation")

        return response.json()

    async def register_admin(
        self, invite_token: str, password: str
    ) -> TokenPair:
        """Register an admin using an invitation token. Returns tokens (auto-login)."""
        if not self.user_service_client:
            raise ValidationError("Admin registration is not configured")

        # Verify and get invite details
        invite_data = await self.verify_admin_invite(invite_token)
        email = invite_data["email"]
        full_name = invite_data["full_name"]

        # Check if user already exists
        existing = await self.credential_repo.get_by_email_or_phone(email, None)
        if existing:
            raise ConflictError("A user with this email already exists")

        validate_password_strength(password)

        # Create credential with ADMIN role
        credential = UserCredential(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            business_id=None,
            is_verified=True,  # Admins are pre-verified via invite
        )
        await self.credential_repo.create(credential)

        # Accept the invitation in user-service (creates role assignment)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.user_service_client._base_url}/internal/admin-invitations/accept",
                    json={"token": invite_token, "user_id": str(credential.id)},
                    headers={"X-Internal-Service": "auth-service"},
                )
            if response.status_code != 200:
                logger.error(
                    f"Failed to accept admin invitation: {response.status_code} {response.text}"
                )
                raise ValidationError("Failed to accept invitation")
        except httpx.ConnectError:
            raise ValidationError("User service is unavailable")
        except httpx.TimeoutException:
            raise ValidationError("User service request timed out")

        # Publish registration event
        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.USER_REGISTERED,
            UserRegisteredPayload(
                user_id=credential.id,
                email=email,
                phone=None,
                role=UserRole.ADMIN,
                business_id=None,
            ).model_dump(mode="json"),
        )

        # Create tokens (auto-login)
        token_pair = self.jwt_handler.create_token_pair(
            user_id=str(credential.id),
            role=credential.role,
            business_id=None,
            email=email,
        )
        token_pair.role = credential.role
        refresh_token_record = RefreshToken(
            user_id=credential.id,
            token_hash=hash_token(token_pair.refresh_token),
            expires_at=utc_now()
            + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
        )
        await self.token_repo.create(refresh_token_record)

        logger.info(
            f"Admin registered: {credential.id}, email={email}, full_name={full_name}"
        )
        return token_pair
