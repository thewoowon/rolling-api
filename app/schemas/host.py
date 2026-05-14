from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models._enums import RoomStatus, RoomType, RoomVisibility
from app.schemas.room import RoomCapacitySummary


class HostRoomItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    subtitle: str | None
    room_type: RoomType
    status: RoomStatus
    region: str
    venue_name: str | None
    venue_address: str | None
    starts_at: datetime
    ends_at: datetime
    min_age: int | None
    max_age: int | None
    male_capacity: int
    female_capacity: int
    price_amount: int
    deposit_amount: int
    currency: str
    application_deadline: datetime | None
    visibility: RoomVisibility
    description: str | None
    viable_at: datetime | None
    planner_id: UUID | None
    payment_instructions: str | None
    created_at: datetime
    updated_at: datetime


class HostRoomDetail(HostRoomItem):
    capacity_summary: RoomCapacitySummary
    viable_threshold: int
    submitted_application_count: int
    confirmed_application_count: int
