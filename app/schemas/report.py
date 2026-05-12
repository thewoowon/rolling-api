from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportCreate(BaseModel):
    reason: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=4000)
    reported_user_id: UUID | None = None
    room_id: UUID | None = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reporter_id: UUID
    reported_user_id: UUID | None
    room_id: UUID | None
    reason: str
    description: str | None
    status: str
    created_at: datetime
