from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models._enums import (
    ApplicationStatus,
    PaymentStatus,
    PlannerStatus,
    ReportStatus,
    RoomStatus,
    RoomType,
    UserRole,
    UserStatus,
)


class AdminDashboard(BaseModel):
    total_users: int
    active_users: int
    blocked_users: int
    total_planners: int
    pending_planners: int
    rooms_by_status: dict[str, int]
    open_reports: int
    paid_payments: int
    completed_rooms_last_30d: int


class AdminUserItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str | None
    phone: str | None
    role: UserRole
    status: UserStatus
    last_login_at: datetime | None
    created_at: datetime
    display_name: str | None = None


class AdminPlannerItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    user_email: str | None
    name: str
    bio: str | None
    region: str | None
    status: PlannerStatus
    rating: float | None
    total_rooms: int
    created_at: datetime


class AdminRoomItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: RoomStatus
    room_type: RoomType
    region: str
    starts_at: datetime
    ends_at: datetime
    male_capacity: int
    female_capacity: int
    price_amount: int
    deposit_amount: int
    planner_id: UUID
    planner_name: str | None = None


class AdminPaymentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    room_id: UUID | None
    application_id: UUID | None
    type: str
    status: PaymentStatus
    provider: str | None
    amount: int
    currency: str
    paid_at: datetime | None
    refunded_at: datetime | None
    created_at: datetime


class AdminReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reporter_id: UUID
    reporter_email: str | None
    reported_user_id: UUID | None
    reported_email: str | None
    room_id: UUID | None
    reason: str
    description: str | None
    status: ReportStatus
    created_at: datetime
    updated_at: datetime


class AdminReportResolution(BaseModel):
    note: str | None = Field(default=None, max_length=4000)


class AdminQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    region: str
    starts_at: datetime
    male_capacity: int
    female_capacity: int
    male_confirmed: int
    female_confirmed: int
    viable_at: datetime | None
    host_user_id: UUID
    host_email: str | None
    host_display_name: str | None
    planner_id: UUID | None
    planner_name: str | None
    status: RoomStatus


class AdminAssignRequest(BaseModel):
    planner_id: UUID


class AdminAuditLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime
