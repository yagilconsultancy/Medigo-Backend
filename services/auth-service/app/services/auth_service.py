import logging
from datetime import timedelta
from uuid import UUID

import httpx

from app.config import settings
from app.models.refresh_token import RefreshToken
from app.models.user_credential import UserCredential
from app.normalization import normalize_email, normalize_phone
from app.repositories.credential_repo import CredentialRepository
from app.repositories.security_settings_repo import SecuritySettingsRepository
from app.repositories.token_repo import TokenRepository
from app.services.otp_service import OTPService
from app.services.security_policy_cache import get_password_policy
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
    UserOTPRequestedPayload,
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

# Failed logins for an unrecognised email have no credential to point at.
# A fixed sentinel keeps those rows joinable/filterable; the previous code
# minted a fresh uuid4() per attempt, which made them permanently orphaned.
UNKNOWN_ADMIN_ID = UUID(int=0)

# A login is flagged suspicious after this many failures for the same email
# inside this window, or on a first-ever success from an unseen IP.
SUSPICIOUS_FAILURE_THRESHOLD = 3
SUSPICIOUS_FAILURE_WINDOW_MINUTES = 15


class AuthService:
    def __init__(
        self,
        credential_repo: CredentialRepository,
        token_repo: TokenRepository,
        otp_service: OTPService,
        jwt_handler: JWTHandler,
        publisher: EventPublisher,
        user_service_client=None,
        login_history_service=None,
    ):
        self.credential_repo = credential_repo
        self.token_repo = token_repo
        self.otp_service = otp_service
        self.jwt_handler = jwt_handler
        self.publisher = publisher
        self.user_service_client = user_service_client
        self.login_history_service = login_history_service

    @staticmethod
    def _verification_details(credential: UserCredential) -> dict:
        return {
            "otp_verified": bool(credential.is_verified),
            "user_id": str(credential.id),
            "next_step": "verify_otp" if not credential.is_verified else None,
        }

    async def _publish_otp_requested(
        self,
        user_id: UUID,
        purpose: str,
        channel: str,
        otp_code: str,
        email: str | None,
        phone: str | None,
    ) -> None:
        await self.publisher.publish(
            Exchanges.AUTH,
            RoutingKeys.USER_OTP_REQUESTED,
            UserOTPRequestedPayload(
                user_id=user_id,
                purpose=purpose,
                channel=channel,
                otp_code=otp_code,
                email=email,
                phone=phone,
            ).model_dump(mode="json"),
        )

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
        email = normalize_email(email)
        phone = normalize_phone(phone)
        await self._validate_password(password)

        # Check if user already exists
        existing = await self.credential_repo.get_by_email_or_phone(email, phone)
        if existing:
            if not existing.is_verified:
                raise ConflictError(
                    "Registration not completed. Please verify your OTP.",
                    details=self._verification_details(existing),
                )
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

        await self._publish_otp_requested(
            user_id=credential.id,
            purpose="registration",
            channel=channel,
            otp_code=otp_code,
            email=email,
            phone=phone,
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
        email = normalize_email(email)
        phone = normalize_phone(phone)
        credential = await self.credential_repo.get_by_email_or_phone(email, phone)
        if not credential:
            raise AuthenticationError("Email or password is not correct")

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
            if credential.failed_attempts + 1 >= await self._max_failed_attempts():
                locked_until = utc_now() + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
                await self.credential_repo.lock_account(credential.id, locked_until)

            # Commit before raising: the AuthenticationError below unwinds
            # through get_db(), which rolls back the request transaction and
            # would otherwise discard the attempt counter and the lock --
            # silently disabling lockout and allowing unlimited brute-force.
            try:
                await self.credential_repo.session.commit()
            except Exception as e:  # never turn a 401 into a 500
                logger.warning(f"Failed to persist failed-login state: {e}")

            raise AuthenticationError("Email or password is not correct")

        # Check if verified
        if not credential.is_verified:
            raise AuthenticationError(
                "Account not verified. Please verify your OTP.",
                details=self._verification_details(credential),
            )

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
        email = normalize_email(email)
        phone = normalize_phone(phone)
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
            raise AuthenticationError("Email or password is not correct")

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
            if credential.failed_attempts + 1 >= await self._max_failed_attempts():
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
            raise AuthenticationError("Email or password is not correct")

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
            raise AuthenticationError(
                "Account not verified. Please verify your OTP.",
                details=self._verification_details(credential),
            )

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
            expire_minutes=await self._admin_session_minutes(),
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

    async def _max_failed_attempts(self) -> int:
        """Lockout threshold from Security Settings, falling back to config."""
        try:
            repo = SecuritySettingsRepository(self.credential_repo.session)
            security_settings = await repo.get_active()
        except Exception:
            logger.warning("Could not load lockout threshold", exc_info=True)
            return settings.MAX_LOGIN_ATTEMPTS
        if not security_settings or not security_settings.max_failed_login_attempts:
            return settings.MAX_LOGIN_ATTEMPTS
        return security_settings.max_failed_login_attempts

    async def _admin_session_minutes(self) -> int | None:
        """Admin session lifetime from Security Settings, in minutes.

        Returns None to fall back to the JWT handler's default when the
        settings row is unavailable.
        """
        try:
            repo = SecuritySettingsRepository(self.credential_repo.session)
            security_settings = await repo.get_active()
        except Exception:
            logger.warning("Could not load session timeout", exc_info=True)
            return None
        if not security_settings or not security_settings.session_timeout_hours:
            return None
        return security_settings.session_timeout_hours * 60

    async def _validate_password(self, password: str) -> None:
        """Validate against the admin-configured policy, not a hardcoded one.

        Falls back to the built-in defaults if the settings row can't be read,
        so a settings problem never blocks registration or password reset.
        """
        policy = await get_password_policy(self.credential_repo.session)
        validate_password_strength(password, policy)

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
        """Record an admin login attempt, durably.

        Failure paths raise immediately after calling this, and that exception
        unwinds through get_db(), which rolls the request transaction back. So
        for unsuccessful attempts we commit here.

        That commit is deliberate and load-bearing: besides the audit row, it
        is what persists the increment_failed_attempts()/lock_account() writes
        made just above by the caller. Without it, `failed_attempts` never
        increments and `locked_until` is never set, which silently disables
        account lockout entirely and allows unlimited password brute-force.
        Do not remove it without replacing it with an independent session.
        """
        if not self.login_history_service:
            return
        try:
            is_suspicious = await self._is_suspicious_login(
                admin_email=admin_email, ip_address=ip_address, success=success
            )
            await self.login_history_service.record_login(
                user_id=user_id or UNKNOWN_ADMIN_ID,
                admin_name=admin_name,
                admin_email=admin_email,
                ip_address=ip_address,
                device_info=device_info,
                success=success,
                failure_reason=failure_reason,
                is_suspicious=is_suspicious,
            )
            if not success:
                await self.login_history_service.session.commit()
        except Exception as e:
            # Audit logging must never turn a clean 401 into a 500.
            logger.warning(f"Failed to record login attempt: {e}")

    async def _is_suspicious_login(
        self, admin_email: str, ip_address: str, success: bool
    ) -> bool:
        """Flag repeated failures, or a first-ever success from a new IP."""
        if not self.login_history_service or not admin_email:
            return False
        repo = self.login_history_service.repo
        try:
            if not success:
                since = utc_now() - timedelta(
                    minutes=SUSPICIOUS_FAILURE_WINDOW_MINUTES
                )
                recent = await repo.count_recent_failures(admin_email, since)
                return recent + 1 >= SUSPICIOUS_FAILURE_THRESHOLD
            if ip_address and ip_address != "unknown":
                return not await repo.has_successful_login_from_ip(
                    admin_email, ip_address
                )
        except Exception as e:
            logger.warning(f"Suspicious-login check failed: {e}")
        return False

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

        # Create new token pair. Admins keep the configured session timeout,
        # otherwise the first refresh silently drops back to the default.
        new_token_pair = self.jwt_handler.create_token_pair(
            user_id=str(credential.id),
            role=credential.role,
            business_id=str(credential.business_id) if credential.business_id else None,
            email=credential.email,
            expire_minutes=(
                await self._admin_session_minutes()
                if credential.role == UserRole.ADMIN
                else None
            ),
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
        await self._validate_password(new_password)

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

    async def verify_password(self, user_id: UUID, password: str) -> None:
        """Verify a user's own password (re-authentication for sensitive actions)."""
        credential = await self.credential_repo.get_by_id(user_id)
        if not credential or not verify_password(password, credential.password_hash):
            raise AuthenticationError("Password is not correct")

    async def resend_otp(self, user_id: UUID, purpose: str) -> str:
        """Resend OTP for a user."""
        credential = await self.credential_repo.get_by_id(user_id)
        if not credential:
            raise NotFoundError("User not found")

        channel = "email" if credential.email else "sms"
        otp_code = await self.otp_service.generate_otp(user_id, purpose, channel)
        # TODO: Consider removing the OTP code from logs in production for security reasons
        print(f"Resending OTP for user {user_id}, purpose={purpose}, channel={channel}, otp_code={otp_code}")
        await self._publish_otp_requested(
            user_id=user_id,
            purpose=purpose,
            channel=channel,
            otp_code=otp_code,
            email=credential.email,
            phone=credential.phone,
        )
        return otp_code

    async def forgot_password(
        self, email: str | None, phone: str | None
    ) -> tuple[UUID, str] | None:
        """Request a password reset via OTP. Returns (user_id, otp_code) or None."""
        email = normalize_email(email)
        phone = normalize_phone(phone)
        credential = await self.credential_repo.get_by_email_or_phone(email, phone)
        if not credential:
            logger.info("Password reset requested for non-existent account")
            return None

        if not credential.is_active:
            return None

        # Generate OTP with password_reset purpose
        channel = "email" if credential.email else "sms"
        otp_code = await self.otp_service.generate_otp(
            credential.id, "password_reset", channel
        )

        # Publish OTP event for notification delivery
        await self._publish_otp_requested(
            user_id=credential.id,
            purpose="password_reset",
            channel=channel,
            otp_code=otp_code,
            email=credential.email,
            phone=credential.phone,
        )

        logger.info(f"Password reset OTP requested for user {credential.id}")
        return credential.id, otp_code

    async def reset_password(
        self, user_id: UUID, code: str, new_password: str
    ) -> None:
        """Reset password using a valid OTP code."""
        await self._validate_password(new_password)

        credential = await self.credential_repo.get_by_id(user_id)
        if not credential:
            raise NotFoundError("User not found")

        # Verify OTP
        await self.otp_service.verify_otp(user_id, code, "password_reset")

        # Update password
        await self.credential_repo.update_password(
            user_id, hash_password(new_password)
        )

        # Revoke all refresh tokens (force re-login)
        await self.token_repo.revoke_all_for_user(user_id)

        logger.info(f"Password reset completed for user {user_id}")

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
        email = normalize_email(invite_data["email"])
        business_id = UUID(invite_data["business_id"])

        # Check if user already exists (admin-created driver)
        existing = await self.credential_repo.get_by_email_or_phone(email, None)
        if existing:
            await self._validate_password(password)

            # Credential was pre-created by admin — update the password from the invitee
            await self.credential_repo.update_password(
                existing.id, hash_password(password)
            )

            # Accept the invitation in user-service
            await self.user_service_client.accept_invitation(
                invite_token, str(existing.id)
            )

            # Ensure account is verified
            if not existing.is_verified:
                await self.credential_repo.update_verified(existing.id, True)

            # Create tokens for the registered driver
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

            logger.info(f"Admin-created driver password updated via register: {existing.id}")
            return token_pair

        await self._validate_password(password)

        # Create credential — a valid invite token is proof of identity, so the
        # driver is verified on activation (no separate email-OTP step).
        credential = UserCredential(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.DRIVER,
            business_id=business_id,
            is_verified=True,
        )
        await self.credential_repo.create(credential)

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

        # Log the driver straight in — activation completes verification.
        token_pair = self.jwt_handler.create_token_pair(
            user_id=str(credential.id),
            role=credential.role,
            business_id=str(credential.business_id) if credential.business_id else None,
            email=credential.email,
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
            f"Driver registered and verified: {credential.id}, business={business_id}"
        )
        return token_pair

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
        email = normalize_email(invite_data["email"])
        full_name = invite_data["full_name"]

        # Check if user already exists
        existing = await self.credential_repo.get_by_email_or_phone(email, None)
        if existing:
            raise ConflictError("A user with this email already exists")

        await self._validate_password(password)

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
