from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from mediride_common.schemas.enums import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(None, min_length=10, max_length=20)
    full_name: str | None = Field(None, min_length=1, max_length=200)
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.RIDER

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        if self.full_name and not (self.first_name and self.last_name):
            parts = self.full_name.strip().split(None, 1)
            self.first_name = self.first_name or parts[0]
            self.last_name = self.last_name or (parts[1] if len(parts) > 1 else "")
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


class VerifyPasswordRequest(BaseModel):
    password: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        return self


class ResetPasswordRequest(BaseModel):
    user_id: UUID
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


class DriverVerifyInviteRequest(BaseModel):
    invite_token: str


class DriverRegisterRequest(BaseModel):
    invite_token: str
    password: str = Field(..., min_length=8, max_length=128)


class AdminVerifyInviteRequest(BaseModel):
    invite_token: str


class AdminRegisterRequest(BaseModel):
    invite_token: str
    password: str = Field(..., min_length=8, max_length=128)


class DriverActivationCheckRequest(BaseModel):
    email: EmailStr


class DriverActivationOTPRequest(BaseModel):
    email: EmailStr


class DriverActivationCompleteRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
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


class ForgotPasswordResponse(BaseModel):
    user_id: UUID
    message: str = "OTP sent for password reset."


class InviteVerifyResponse(BaseModel):
    valid: bool
    fleet_name: str | None = None
    email: str | None = None


class DriverActivationCheckResponse(BaseModel):
    # not_activated -> tell the driver to email support
    # set_password  -> approved, first time: needs emailed code + new password
    # login         -> approved and password already set: normal login
    next_step: str
    message: str | None = None
