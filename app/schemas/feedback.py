from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=4000)
    safety_rating: int | None = Field(default=None, ge=1, le=5)
    planner_rating: int | None = Field(default=None, ge=1, le=5)
    would_join_again: bool | None = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    user_id: UUID
    rating: int
    comment: str | None
    safety_rating: int | None
    planner_rating: int | None
    would_join_again: bool | None
    created_at: datetime
