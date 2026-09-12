import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.models.account_deletion_request import AccountDeletionRequest
from app.repositories.account_deletion_request_repo import (
    AccountDeletionRequestRepository,
)
from app.repositories.user_repo import UserRepository
from app.services.user_service import UserService
from mediride_common.config import BaseServiceSettings
from mediride_common.events.constants import Exchanges, RoutingKeys
from mediride_common.events.publisher import EventPublisher
from mediride_common.exceptions import ConflictError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

# Identical wording for every outcome of the submit/resend endpoints. The form
# is public, so a response that differed when the email was unknown would turn
# it into an oracle for "is this address a MediGo user?".
GENERIC_SUBMIT_MESSAGE = (
    "If an account exists for that email address, we have sent it a 6-digit "
    "verification code. Enter the code to confirm your deletion request."
)

# Deliberately vague: it does not distinguish wrong code from expired code
# from no-such-request.
INVALID_CODE_MESSAGE = (
    "That code is not valid or has expired. Request a new code and try again."
)


class AccountDeletionRequestService:
    """Public account-deletion requests and their admin review.

    Flow: the requester submits the public form, proves control of the mailbox
    with an emailed OTP, and an admin then approves - which runs the same
    soft-delete as the in-app Delete Account button - or rejects.
    """

    OTP_TTL_MINUTES = 15
    OTP_MAX_ATTEMPTS = 5
    OTP_MAX_SENDS = 5
    OTP_RESEND_COOLDOWN_SECONDS = 60
    MAX_REQUESTS_PER_EMAIL_PER_DAY = 5

    def __init__(
        self,
        request_repo: AccountDeletionRequestRepository,
        user_repo: UserRepository,
        user_service: UserService,
        publisher: EventPublisher | None = None,
        settings: BaseServiceSettings | None = None,
    ):
        self.request_repo = request_repo
        self.user_repo = user_repo
        self.user_service = user_service
        self.publisher = publisher
        self._settings = settings

    # --- OTP helpers ---

    def _hash_code(self, code: str, request_id: UUID) -> str:
        """HMAC the code, keyed on the service secret and salted per request.

        Six digits is a tiny search space, so a bare SHA-256 of the code would
        be trivially reversible from a database dump. Keying on JWT_SECRET_KEY
        means a leaked table alone yields nothing, and mixing in the request id
        stops one precomputed table covering every row.
        """
        secret = ""
        if self._settings is not None:
            secret = getattr(self._settings, "JWT_SECRET_KEY", "") or ""
        return hmac.new(
            secret.encode(),
            f"{request_id}:{code}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def _issue_code(self, request: AccountDeletionRequest) -> str:
        code = f"{secrets.randbelow(1_000_000):06d}"
        now = datetime.now(timezone.utc)
        request.otp_code_hash = self._hash_code(code, request.id)
        request.otp_expires_at = now + timedelta(minutes=self.OTP_TTL_MINUTES)
        request.otp_attempts = 0
        request.otp_sent_count = (request.otp_sent_count or 0) + 1
        request.otp_last_sent_at = now
        return code

    def _can_send_now(self, request: AccountDeletionRequest) -> bool:
        if (request.otp_sent_count or 0) >= self.OTP_MAX_SENDS:
            return False
        if request.otp_last_sent_at is None:
            return True
        elapsed = (
            datetime.now(timezone.utc) - _as_utc(request.otp_last_sent_at)
        ).total_seconds()
        return elapsed >= self.OTP_RESEND_COOLDOWN_SECONDS

    async def _publish(self, routing_key: str, payload: dict) -> None:
        if not self.publisher:
            logger.warning(
                "No event publisher configured; skipping %s event", routing_key
            )
            return
        await self.publisher.publish(
            exchange_name=Exchanges.USERS,
            routing_key=routing_key,
            payload=payload,
        )

    # --- Public flow ---

    async def submit_request(
        self,
        full_name: str,
        email: str,
        phone: str | None,
        reason: str | None,
        ip_address: str | None = None,
    ) -> str:
        """Create or refresh a deletion request and email a verification code.

        Always returns the same message. Callers must not branch on it.
        """
        email = email.strip().lower()

        recent = await self.request_repo.count_recent_for_email(
            email, datetime.now(timezone.utc) - timedelta(days=1)
        )
        if recent >= self.MAX_REQUESTS_PER_EMAIL_PER_DAY:
            logger.warning(
                "Account deletion request throttled for %s (%s in last 24h)",
                email,
                recent,
            )
            return GENERIC_SUBMIT_MESSAGE

        user = await self.user_repo.get_by_email_ci(email)
        if not user:
            # No row is written: the admin queue should only ever hold
            # requests that can actually be actioned.
            logger.info(
                "Account deletion request for unknown email %s - no action taken",
                email,
            )
            return GENERIC_SUBMIT_MESSAGE

        existing = await self.request_repo.get_active_by_email(email)

        if existing and existing.status == AccountDeletionRequest.STATUS_PENDING_REVIEW:
            # Already verified and sitting in the review queue. Re-submitting
            # must not reopen it or spam a fresh code.
            logger.info(
                "Account deletion request %s for %s already awaiting review",
                existing.id,
                email,
            )
            return GENERIC_SUBMIT_MESSAGE

        if existing:
            request = existing
            request.full_name = full_name
            request.phone = phone
            request.reason = reason
            request.ip_address = ip_address
            request.user_id = user.id
        else:
            request = AccountDeletionRequest(
                full_name=full_name,
                email=email,
                phone=phone,
                reason=reason,
                user_id=user.id,
                status=AccountDeletionRequest.STATUS_PENDING_VERIFICATION,
                ip_address=ip_address,
            )
            request = await self.request_repo.create(request)

        if not self._can_send_now(request):
            logger.warning(
                "Suppressing deletion OTP for request %s (cooldown or send cap)",
                request.id,
            )
            return GENERIC_SUBMIT_MESSAGE

        code = self._issue_code(request)
        await self.request_repo.session.flush()

        await self._publish(
            RoutingKeys.ACCOUNT_DELETION_OTP_REQUESTED,
            {
                "request_id": str(request.id),
                "email": request.email,
                "full_name": request.full_name,
                "otp_code": code,
                "expires_in_minutes": self.OTP_TTL_MINUTES,
            },
        )
        logger.info("Issued account deletion OTP for request %s", request.id)
        return GENERIC_SUBMIT_MESSAGE

    async def resend_code(self, email: str) -> str:
        email = email.strip().lower()
        request = await self.request_repo.get_active_by_email(email)

        if (
            not request
            or request.status != AccountDeletionRequest.STATUS_PENDING_VERIFICATION
            or not self._can_send_now(request)
        ):
            logger.info("Deletion OTP resend not issued for %s", email)
            return GENERIC_SUBMIT_MESSAGE

        code = self._issue_code(request)
        await self.request_repo.session.flush()

        await self._publish(
            RoutingKeys.ACCOUNT_DELETION_OTP_REQUESTED,
            {
                "request_id": str(request.id),
                "email": request.email,
                "full_name": request.full_name,
                "otp_code": code,
                "expires_in_minutes": self.OTP_TTL_MINUTES,
            },
        )
        logger.info("Resent account deletion OTP for request %s", request.id)
        return GENERIC_SUBMIT_MESSAGE

    async def verify_code(self, email: str, code: str) -> AccountDeletionRequest:
        email = email.strip().lower()
        request = await self.request_repo.get_active_by_email(email)

        if not request:
            raise ValidationError(INVALID_CODE_MESSAGE)

        # Verifying twice is not an error - the requester may have refreshed
        # the confirmation page - so hand back the same result.
        if request.status == AccountDeletionRequest.STATUS_PENDING_REVIEW:
            return request

        if not request.otp_code_hash or not request.otp_expires_at:
            raise ValidationError(INVALID_CODE_MESSAGE)

        if request.otp_attempts >= self.OTP_MAX_ATTEMPTS:
            raise ValidationError(
                "Too many incorrect attempts. Request a new code to continue."
            )

        if datetime.now(timezone.utc) > _as_utc(request.otp_expires_at):
            raise ValidationError(INVALID_CODE_MESSAGE)

        expected = self._hash_code(code, request.id)
        if not hmac.compare_digest(expected, request.otp_code_hash):
            request.otp_attempts += 1
            await self.request_repo.session.flush()
            logger.warning(
                "Bad deletion OTP for request %s (attempt %s)",
                request.id,
                request.otp_attempts,
            )
            raise ValidationError(INVALID_CODE_MESSAGE)

        now = datetime.now(timezone.utc)
        request.email_verified_at = now
        request.status = AccountDeletionRequest.STATUS_PENDING_REVIEW
        # The code has done its job; keeping it around only widens the window
        # in which a leak would matter.
        request.otp_code_hash = None
        request.otp_expires_at = None
        await self.request_repo.session.flush()

        await self._publish(
            RoutingKeys.ACCOUNT_DELETION_REQUEST_RECEIVED,
            {
                "request_id": str(request.id),
                "email": request.email,
                "full_name": request.full_name,
            },
        )
        logger.info("Account deletion request %s verified", request.id)
        return request

    # --- Admin review ---

    async def list_requests(
        self,
        status_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AccountDeletionRequest], int]:
        return await self.request_repo.list_all(
            status_filter=status_filter, search=search, offset=offset, limit=limit
        )

    async def get_request(self, request_id: UUID) -> AccountDeletionRequest:
        request = await self.request_repo.get_by_id(request_id)
        if not request:
            raise NotFoundError("Deletion request not found")
        return request

    async def get_kpis(self) -> dict:
        return await self.request_repo.get_kpis()

    async def approve_request(
        self, request_id: UUID, admin_id: UUID, notes: str | None = None
    ) -> AccountDeletionRequest:
        request = await self.get_request(request_id)

        if request.status != AccountDeletionRequest.STATUS_PENDING_REVIEW:
            raise ConflictError(
                f"Only verified requests awaiting review can be approved "
                f"(this one is '{request.status}')"
            )

        # Soft-deletes the profile and deactivates the auth credentials - the
        # same path as the in-app Delete Account button.
        try:
            await self.user_service.delete_account(request.user_id)
        except NotFoundError:
            # The account went away between verification and review (deleted
            # in-app, or removed by another admin). The request is still
            # satisfied, so record it as approved rather than failing.
            logger.info(
                "Account %s for deletion request %s was already deleted",
                request.user_id,
                request.id,
            )

        now = datetime.now(timezone.utc)
        request.status = AccountDeletionRequest.STATUS_APPROVED
        request.reviewed_by = admin_id
        request.reviewed_at = now
        request.admin_notes = notes
        await self.request_repo.session.flush()

        await self._publish(
            RoutingKeys.ACCOUNT_DELETION_APPROVED,
            {
                "request_id": str(request.id),
                "email": request.email,
                "full_name": request.full_name,
            },
        )
        logger.info(
            "Account deletion request %s approved by %s", request.id, admin_id
        )
        return request

    async def reject_request(
        self, request_id: UUID, admin_id: UUID, reason: str
    ) -> AccountDeletionRequest:
        request = await self.get_request(request_id)

        if request.status != AccountDeletionRequest.STATUS_PENDING_REVIEW:
            raise ConflictError(
                f"Only verified requests awaiting review can be rejected "
                f"(this one is '{request.status}')"
            )

        now = datetime.now(timezone.utc)
        request.status = AccountDeletionRequest.STATUS_REJECTED
        request.reviewed_by = admin_id
        request.reviewed_at = now
        request.rejection_reason = reason
        await self.request_repo.session.flush()

        await self._publish(
            RoutingKeys.ACCOUNT_DELETION_REJECTED,
            {
                "request_id": str(request.id),
                "email": request.email,
                "full_name": request.full_name,
                "reason": reason,
            },
        )
        logger.info(
            "Account deletion request %s rejected by %s", request.id, admin_id
        )
        return request


def _as_utc(value: datetime) -> datetime:
    """Treat a naive timestamp as UTC.

    Columns are timestamptz, but SQLite in tests (and a row just built in
    Python) can hand back naive datetimes, which would raise on comparison.
    """
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
