from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from mediride_common.schemas.enums import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(None, min_length=10, max_length=20)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.RIDER

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        return self


class LoginRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        return self


class VerifyOTPRequest(BaseModel):
    user_id: UUID
    code: str = Field(..., min_length=6, max_length=6)
    purpose: str = "registration"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        return self


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class DriverVerifyInviteRequest(BaseModel):
    invite_token: str


class DriverRegisterRequest(BaseModel):
    invite_token: str
    password: str = Field(..., min_length=8, max_length=128)


# Response schemas
class RegisterResponse(BaseModel):
    user_id: UUID
    message: str = "Registration successful. Please verify your account."


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class OTPVerifyResponse(BaseModel):
    verified: bool = True
    message: str = "Account verified successfully"


class InviteVerifyResponse(BaseModel):
    valid: bool
    fleet_name: str | None = None
    email: str | None = None
