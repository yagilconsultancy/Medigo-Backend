from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SubmitRatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=1000)
    rating_type: str


class RatingResponse(BaseModel):
    id: UUID
    ride_id: UUID
    rated_user_id: UUID
    rated_by_user_id: UUID
    rating_type: str
    rating: int
    comment: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
