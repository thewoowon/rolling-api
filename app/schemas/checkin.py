from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models._enums import CheckInStatus, Gender


class CheckInPlannerItem(BaseModel):
    """Planner-side check-in row, joined with participant profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    application_id: UUID
    status: CheckInStatus
    checked_in_at: datetime | None
    check_in_code: str | None
    display_name: str | None
    gender: Gender | None
    birth_year: int | None
    region: str | None


class MyCheckInView(BaseModel):
    """Participant-side: their own check-in for a room."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    status: CheckInStatus
    check_in_code: str | None
    checked_in_at: datetime | None
