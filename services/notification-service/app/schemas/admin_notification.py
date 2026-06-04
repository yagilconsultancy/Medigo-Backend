from uuid import UUID

from pydantic import BaseModel, Field


class SendDriverNotificationRequest(BaseModel):
    driver_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)


class SendDriverNotificationResponse(BaseModel):
    notification_id: UUID
    driver_id: UUID
    email_sent: bool
    push_sent: bool


class SendRiderNotificationRequest(BaseModel):
    rider_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)


class SendRiderNotificationResponse(BaseModel):
    notification_id: UUID
    rider_id: UUID
    email_sent: bool
    push_sent: bool
