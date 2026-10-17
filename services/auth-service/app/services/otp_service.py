import hashlib
import hmac
import logging
from datetime import timedelta
from uuid import UUID

from app.config import settings
from app.models.otp import OTPRecord
from app.repositories.otp_repo import OTPRepository
from mediride_common.exceptions import RateLimitError, ValidationError
from mediride_common.utils import generate_otp, utc_now


logger = logging.getLogger(__name__)

# Codes are stored as a keyed hash, so a copy of the database does not reveal
# live codes. Rows written before this change hold the plain 6 digit code and
# are still accepted until they expire.
_HASH_PREFIX = "h1:"


def hash_otp(user_id: UUID, purpose: str, code: str) -> str:
    message = f"{user_id}:{purpose}:{code}".encode()
    digest = hmac.new(
        settings.JWT_SECRET_KEY.encode(), message, hashlib.sha256
    ).hexdigest()
    return _HASH_PREFIX + digest


def _code_matches(otp, user_id: UUID, purpose: str, code: str) -> bool:
    stored = otp.code or ""
    if stored.startswith(_HASH_PREFIX):
        expected = hash_otp(user_id, purpose, code)
    else:
        expected = code
    return hmac.compare_digest(stored.encode(), expected.encode())


class OTPService:
    def __init__(self, otp_repo: OTPRepository):
        self.otp_repo = otp_repo

    async def generate_otp(
        self,
        user_id: UUID,
        purpose: str,
        channel: str,
        expire_minutes: int | None = None,
    ) -> str:
        # Rate limit: max OTP requests per hour
        # Counted per purpose, so spamming one flow cannot use up the quota
        # of another (for example blocking a real password reset).
        recent_count = await self.otp_repo.count_recent_for_user(
            user_id, purpose=purpose
        )
        if recent_count >= settings.OTP_MAX_REQUESTS_PER_HOUR:
            raise RateLimitError("Too many OTP requests. Please try again later.")

        code = generate_otp()

        otp = OTPRecord(
            user_id=user_id,
            code=hash_otp(user_id, purpose, code),
            purpose=purpose,
            channel=channel,
            expires_at=utc_now()
            + timedelta(minutes=expire_minutes or settings.OTP_EXPIRE_MINUTES),
        )
        await self.otp_repo.create(otp)
        return code

    async def verify_otp(self, user_id: UUID, code: str, purpose: str) -> bool:
        otp = await self.otp_repo.get_latest_unverified(user_id, purpose)
        if not otp:
            raise ValidationError("No pending OTP found or OTP has expired")

        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise ValidationError("Maximum OTP attempts exceeded. Request a new code.")

        await self.otp_repo.increment_attempts(otp.id)

        if not _code_matches(otp, user_id, purpose, code):
            # Commit before raising: the ValidationError unwinds through
            # get_db(), which rolls the request transaction back and would
            # otherwise discard the attempt counter, leaving unlimited guesses.
            try:
                await self.otp_repo.session.commit()
            except Exception:  # never turn a 400 into a 500
                logger.warning("Failed to persist OTP attempt counter", exc_info=True)
            raise ValidationError("Invalid OTP code")

        await self.otp_repo.mark_verified(otp.id)
        return True
