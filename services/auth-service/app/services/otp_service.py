from datetime import timedelta
from uuid import UUID

from app.config import settings
from app.models.otp import OTPRecord
from app.repositories.otp_repo import OTPRepository
from mediride_common.exceptions import RateLimitError, ValidationError
from mediride_common.utils import generate_otp, utc_now


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
        recent_count = await self.otp_repo.count_recent_for_user(user_id)
        if recent_count >= settings.OTP_MAX_REQUESTS_PER_HOUR:
            raise RateLimitError("Too many OTP requests. Please try again later.")

        code = generate_otp()

        otp = OTPRecord(
            user_id=user_id,
            code=code,
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

        if otp.code != code:
            raise ValidationError("Invalid OTP code")

        await self.otp_repo.mark_verified(otp.id)
        return True
