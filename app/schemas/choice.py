from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models._enums import ChoiceType, Gender, MatchStatus


class ChoiceTarget(BaseModel):
    """Opposite-gender attendee a participant can choose for the room."""

    user_id: UUID
    display_name: str | None
    gender: Gender | None
    birth_year: int | None
    region: str | None
    job_title: str | None
    intro: str | None
    my_choice: ChoiceType | None = None


class ChoiceItem(BaseModel):
    chosen_id: UUID
    choice_type: ChoiceType
    note: str | None = Field(default=None, max_length=2000)


class ChoiceSubmission(BaseModel):
    choices: list[ChoiceItem] = Field(min_length=1)


class ChoiceSubmissionResult(BaseModel):
    accepted: int
    new_mutual_matches: int


class MatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    status: MatchStatus
    counterpart_user_id: UUID
    counterpart_name: str | None
    counterpart_gender: Gender | None
    counterpart_birth_year: int | None
    counterpart_region: str | None
    counterpart_job_title: str | None
    counterpart_intro: str | None
    after_proposed: bool
    created_at: datetime
    updated_at: datetime


class AfterDateProposalCreate(BaseModel):
    proposed_date: datetime | None = None
    proposed_place: str | None = Field(default=None, max_length=2000)


class AfterDateProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    match_result_id: UUID
    proposer_id: UUID
    proposed_date: datetime | None
    proposed_place: str | None
    status: str
    created_at: datetime
    updated_at: datetime
