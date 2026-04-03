from uuid import UUID

from pydantic import BaseModel

from mediride_common.schemas.enums import UserRole


class TokenPayload(BaseModel):
    sub: str
    role: UserRole
    business_id: str | None = None
    email: str | None = None
    jti: str
    exp: int
    iat: int
    type: str = "access"


class UserClaims(BaseModel):
    id: UUID
    role: UserRole
    business_id: UUID | None = None
    email: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str = ""
