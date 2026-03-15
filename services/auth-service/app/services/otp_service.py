import logging

from datetime import timedelta
from uuid import UUID

from app.config import settings
from app.models.otp import OTPRecord
from app.repositories.otp_repo import OTPRepository
from mediride_common.exceptions import RateLimitError, ValidationError
from mediride_common.utils import generate_otp, utc_now

logger = logging.getLogger(__name__)

# Default OTP for development (when email/SMS is not configured)
DEV_DEFAULT_OTP = "123456"


class OTPService:
    def __init__(self, otp_repo: OTPRepository):
        self.otp_repo = otp_repo

    async def generate_otp(
        self, user_id: UUID, purpose: str, channel: str
    ) -> str:
        # Rate limit: max OTP requests per hour
        recent_count = await self.otp_repo.count_recent_for_user(user_id)
        if recent_count >= settings.OTP_MAX_REQUESTS_PER_HOUR:
            raise RateLimitError("Too many OTP requests. Please try again later.")

        # Use fixed OTP when email/SMS is not configured (dev/staging)
        if settings.ENVIRONMENT != "production":
            code = DEV_DEFAULT_OTP
            logger.info(f"[DEV] Using default OTP: {code} for user {user_id}")
        else:
            code = generate_otp()

        otp = OTPRecord(
            user_id=user_id,
            code=code,
            purpose=purpose,
            channel=channel,
            expires_at=utc_now() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
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

        if otp.code != code:
            raise ValidationError("Invalid OTP code")

        await self.otp_repo.mark_verified(otp.id)
        return True
