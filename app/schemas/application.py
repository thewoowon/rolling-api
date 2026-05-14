from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models._enums import ApplicationStatus, Gender, RoomStatus, RoomType


class RoomBriefForApplication(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    subtitle: str | None
    region: str
    starts_at: datetime
    ends_at: datetime
    status: RoomStatus
    room_type: RoomType
    venue_name: str | None
    price_amount: int
    deposit_amount: int
    # Only meaningful for approved+ applications. FE decides when to display.
    payment_instructions: str | None = None


class ApplicationCreate(BaseModel):
    applicant_message: str | None = Field(default=None, max_length=2000)


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    room_id: UUID
    user_id: UUID
    status: ApplicationStatus
    applicant_message: str | None
    planner_note: str | None
    approved_at: datetime | None
    rejected_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MyApplicationItem(ApplicationResponse):
    room: RoomBriefForApplication


class ApplicantBrief(BaseModel):
    """Applicant snapshot visible to planner."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID  # application id
    user_id: UUID
    status: ApplicationStatus
    applicant_message: str | None
    planner_note: str | None
    created_at: datetime
    display_name: str | None
    gender: Gender | None
    birth_year: int | None
    region: str | None
    job_title: str | None
    intro: str | None
    profile_image_url: str | None


class PlannerNoteUpdate(BaseModel):
    planner_note: str | None = Field(default=None, max_length=2000)
