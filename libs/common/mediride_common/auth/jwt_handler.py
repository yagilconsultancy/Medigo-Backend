import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from mediride_common.auth.models import TokenPayload, TokenPair, UserClaims
from mediride_common.exceptions import AuthenticationError
from mediride_common.schemas.enums import UserRole


class JWTHandler:
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

    def create_access_token(
        self,
        user_id: str,
        role: UserRole,
        business_id: str | None = None,
        email: str | None = None,
        expire_minutes: int | None = None,
    ) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(
            minutes=expire_minutes or self.access_token_expire_minutes
        )
        payload = {
            "sub": user_id,
            "role": role,
            "business_id": business_id,
            "email": email,
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "access",
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        now = datetime.now(UTC)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        payload = {
            "sub": user_id,
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "refresh",
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_token_pair(
        self,
        user_id: str,
        role: UserRole,
        business_id: str | None = None,
        email: str | None = None,
        expire_minutes: int | None = None,
    ) -> TokenPair:
        """`expire_minutes` overrides the default access-token lifetime.

        Used to honour the admin-configured session_timeout_hours. It must
        also flow into `expires_in`, or the client refreshes on the wrong
        schedule.
        """
        effective_minutes = expire_minutes or self.access_token_expire_minutes
        access_token = self.create_access_token(
            user_id, role, business_id, email, expire_minutes=effective_minutes
        )
        refresh_token = self.create_refresh_token(user_id)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=effective_minutes * 60,
        )

    def decode_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return TokenPayload(**payload)
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {e}")

    def decode_to_claims(self, token: str) -> UserClaims:
        payload = self.decode_token(token)
        if payload.type != "access":
            raise AuthenticationError("Invalid token type")
        return UserClaims(
            id=payload.sub,
            role=payload.role,
            business_id=payload.business_id if payload.business_id else None,
            email=payload.email,
        )
