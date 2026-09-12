from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AccountDeletionRequestCreate(BaseModel):
    """Public deletion request form - no authentication required."""

    full_name: str = Field(..., min_length=1, max_length=255, description="Full Name")
    email: EmailStr = Field(..., description="Email address on the MediGo account")
    phone: str | None = Field(None, max_length=20, description="Registered phone number")
    reason: str | None = Field(None, max_length=2000, description="Reason for request (optional)")
    confirm_understanding: bool = Field(
        ...,
        description="Requester confirms the deletion is permanent and cannot be undone",
    )


class AccountDeletionVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class AccountDeletionResendRequest(BaseModel):
    email: EmailStr


class AccountDeletionPublicResponse(BaseModel):
    """Deliberately free of account details.

    Every public response is identical whether or not the email matches an
    account, so this endpoint cannot be used to test which emails are
    registered with MediGo.
    """

    message: str


class AccountDeletionVerifiedResponse(BaseModel):
    """Returned once the emailed code checks out.

    The reference is the request id, which the requester can quote to support;
    it only becomes known after proving control of the mailbox.
    """

    reference: UUID
    status: str
    submitted_at: datetime
    message: str = (
        "Your deletion request has been verified and sent to our team for review. "
        "You will receive a confirmation email once it has been processed."
    )


class RejectDeletionRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class ApproveDeletionRequest(BaseModel):
    notes: str | None = None


class AccountDeletionRequestResponse(BaseModel):
    """Admin-facing view of a deletion request."""

    id: UUID
    full_name: str
    email: str
    phone: str | None = None
    reason: str | None = None
    user_id: UUID
    status: str
    email_verified_at: datetime | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    admin_notes: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime

    # Resolved from the linked account so an admin can eyeball whether the
    # form details actually match the account being deleted.
    account_email: str | None = None
    account_phone: str | None = None
    account_name: str | None = None
    account_role: str | None = None
    account_created_at: datetime | None = None
    account_deleted_at: datetime | None = None
    reviewer_name: str | None = None

    model_config = {"from_attributes": True}


class AccountDeletionKPIs(BaseModel):
    total_requests: int
    pending_review: int
    approved: int
    rejected: int
    awaiting_verification: int
