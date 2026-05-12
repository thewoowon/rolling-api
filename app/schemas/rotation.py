from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models._enums import (
    Gender,
    RotationRoundStatus,
    RotationSessionStatus,
)


class SeatPair(BaseModel):
    table_number: int
    participant_a_id: UUID
    participant_b_id: UUID
    participant_a_name: str | None = None
    participant_b_name: str | None = None


class RoundView(BaseModel):
    id: UUID
    round_number: int
    status: RotationRoundStatus
    starts_at: datetime | None
    ends_at: datetime | None
    seats: list[SeatPair]


class RotationSessionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    status: RotationSessionStatus
    current_round: int
    round_duration_minutes: int
    started_at: datetime | None
    ended_at: datetime | None
    rounds: list[RoundView]


class RotationStartRequest(BaseModel):
    round_duration_minutes: int = 12


class OpponentBrief(BaseModel):
    user_id: UUID
    display_name: str | None
    gender: Gender | None
    birth_year: int | None
    region: str | None
    job_title: str | None
    intro: str | None


class MyCurrentRoundView(BaseModel):
    """Participant view of the current round."""

    session_status: RotationSessionStatus
    current_round: int
    total_rounds: int
    round_duration_minutes: int
    table_number: int | None = None
    opponent: OpponentBrief | None = None
    round_status: RotationRoundStatus | None = None
