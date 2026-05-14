from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models._enums import RoomStatus, RoomType, RoomVisibility


class PlannerBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    bio: str | None = None
    region: str | None = None
    rating: float | None = None
    total_rooms: int


class RoomCapacitySummary(BaseModel):
    male_capacity: int
    female_capacity: int
    male_confirmed: int = 0
    female_confirmed: int = 0
    male_paid: int = 0
    female_paid: int = 0


class RoomListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    subtitle: str | None
    room_type: RoomType
    status: RoomStatus
    region: str
    starts_at: datetime
    ends_at: datetime
    min_age: int | None
    max_age: int | None
    price_amount: int
    deposit_amount: int
    currency: str
    male_capacity: int
    female_capacity: int
    application_deadline: datetime | None
    planner: PlannerBrief


class RoomDetail(RoomListItem):
    description: str | None
    venue_name: str | None
    venue_address: str | None
    visibility: RoomVisibility
    capacity_summary: RoomCapacitySummary


class RoomListResponse(BaseModel):
    items: list[RoomListItem]
    total: int
    limit: int
    offset: int


class RoomCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    subtitle: str | None = Field(default=None, max_length=255)
    description: str | None = None
    room_type: RoomType
    region: str = Field(min_length=1, max_length=100)
    venue_name: str | None = Field(default=None, max_length=150)
    venue_address: str | None = None
    starts_at: datetime
    ends_at: datetime
    min_age: int | None = Field(default=None, ge=18, le=99)
    max_age: int | None = Field(default=None, ge=18, le=99)
    male_capacity: int = Field(ge=1, le=20)
    female_capacity: int = Field(ge=1, le=20)
    price_amount: int = Field(ge=0)
    deposit_amount: int = Field(ge=0)
    currency: str = Field(default="KRW", min_length=3, max_length=10)
    application_deadline: datetime | None = None
    visibility: RoomVisibility = RoomVisibility.PUBLIC
    payment_instructions: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _check(self) -> "RoomCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.min_age is not None and self.max_age is not None and self.min_age > self.max_age:
            raise ValueError("min_age must be <= max_age")
        if self.application_deadline and self.application_deadline > self.starts_at:
            raise ValueError("application_deadline must be on or before starts_at")
        return self


class RoomUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=150)
    subtitle: str | None = Field(default=None, max_length=255)
    description: str | None = None
    region: str | None = Field(default=None, max_length=100)
    venue_name: str | None = Field(default=None, max_length=150)
    venue_address: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    min_age: int | None = Field(default=None, ge=18, le=99)
    max_age: int | None = Field(default=None, ge=18, le=99)
    male_capacity: int | None = Field(default=None, ge=1, le=20)
    female_capacity: int | None = Field(default=None, ge=1, le=20)
    price_amount: int | None = Field(default=None, ge=0)
    deposit_amount: int | None = Field(default=None, ge=0)
    application_deadline: datetime | None = None
    visibility: RoomVisibility | None = None
    payment_instructions: str | None = Field(default=None, max_length=2000)
