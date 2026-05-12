"""Planner = Rolling-affiliated operator. After admin assigns a VIABLE room
to them, they confirm it and operate check-in/rotation."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    APIError,
    Forbidden,
    InvalidStateTransition,
    NotFound,
)
from app.models import (
    CheckIn,
    Planner,
    Room,
    RoomApplication,
    User,
)
from app.models._enums import (
    ApplicationStatus,
    CheckInStatus,
    PlannerStatus,
    RoomStatus,
)
from app.schemas.planner import PlannerDashboard
from app.services import host_service


CONFIRMABLE_FROM = (RoomStatus.ASSIGNED.value,)


async def get_planner_for_user(db: AsyncSession, user: User) -> Planner:
    planner = await db.scalar(select(Planner).where(Planner.user_id == user.id))
    if planner is None:
        raise Forbidden("This account is not registered as a planner.")
    if planner.status != PlannerStatus.APPROVED.value:
        raise Forbidden(f"Planner is {planner.status}.")
    return planner


async def _get_assigned_room(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> Room:
    """Planner can only operate rooms that admin assigned to them."""
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.planner_id != planner.id:
        raise Forbidden("This room is not assigned to you.")
    return room


async def list_assigned_rooms(db: AsyncSession, planner: Planner) -> list[Room]:
    rows = await db.scalars(
        select(Room)
        .where(Room.planner_id == planner.id)
        .order_by(Room.starts_at.asc())
    )
    return list(rows.all())


async def get_assigned_room(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> Room:
    return await _get_assigned_room(db, planner, room_id)


async def confirm_room(db: AsyncSession, planner: Planner, room_id: UUID) -> Room:
    """Planner accepts the assignment and locks the roster: ASSIGNED → CONFIRMED."""
    room = await _get_assigned_room(db, planner, room_id)
    if room.status not in CONFIRMABLE_FROM:
        raise InvalidStateTransition(
            f"Cannot confirm room in '{room.status}' state."
        )
    summary = await host_service.get_capacity_summary(db, room.id, room)
    confirmed_total = summary.male_confirmed + summary.female_confirmed
    if confirmed_total == 0:
        raise APIError(
            "ROOM_NOT_READY",
            "No confirmed participants yet.",
            status_code=409,
        )
    if summary.male_confirmed > summary.male_capacity:
        raise APIError(
            "OVER_CAPACITY",
            f"Male confirmed ({summary.male_confirmed}) exceeds capacity ({summary.male_capacity}).",
            status_code=409,
        )
    if summary.female_confirmed > summary.female_capacity:
        raise APIError(
            "OVER_CAPACITY",
            f"Female confirmed ({summary.female_confirmed}) exceeds capacity ({summary.female_capacity}).",
            status_code=409,
        )
    room.status = RoomStatus.CONFIRMED.value
    await db.flush()
    return room


async def get_room_summary_counts(db: AsyncSession, room: Room):
    summary = await host_service.get_capacity_summary(db, room.id, room)
    submitted = (
        await db.scalar(
            select(func.count())
            .select_from(RoomApplication)
            .where(RoomApplication.room_id == room.id)
        )
    ) or 0
    confirmed = summary.male_confirmed + summary.female_confirmed
    return summary, int(confirmed), int(submitted)


async def dashboard_counts(db: AsyncSession, planner: Planner) -> PlannerDashboard:
    now = datetime.now(timezone.utc)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    upcoming = (
        await db.scalar(
            select(func.count())
            .select_from(Room)
            .where(
                Room.planner_id == planner.id,
                Room.status.in_(
                    (
                        RoomStatus.ASSIGNED.value,
                        RoomStatus.CONFIRMED.value,
                    )
                ),
                Room.starts_at >= now,
            )
        )
    ) or 0
    in_progress = (
        await db.scalar(
            select(func.count())
            .select_from(Room)
            .where(
                Room.planner_id == planner.id,
                Room.status == RoomStatus.IN_PROGRESS.value,
            )
        )
    ) or 0
    completed = (
        await db.scalar(
            select(func.count())
            .select_from(Room)
            .where(
                Room.planner_id == planner.id,
                Room.status == RoomStatus.COMPLETED.value,
            )
        )
    ) or 0
    # New definition: rooms freshly assigned to me that I haven't confirmed yet.
    pending_assignments = (
        await db.scalar(
            select(func.count())
            .select_from(Room)
            .where(
                Room.planner_id == planner.id,
                Room.status == RoomStatus.ASSIGNED.value,
            )
        )
    ) or 0
    today_checkins = (
        await db.scalar(
            select(func.count())
            .select_from(CheckIn)
            .join(Room, Room.id == CheckIn.room_id)
            .where(
                Room.planner_id == planner.id,
                CheckIn.status == CheckInStatus.CHECKED_IN.value,
                CheckIn.checked_in_at.between(today_start, today_end),
            )
        )
    ) or 0
    return PlannerDashboard(
        upcoming_rooms=int(upcoming),
        in_progress_rooms=int(in_progress),
        pending_applications=int(pending_assignments),
        today_checkins=int(today_checkins),
        completed_rooms=int(completed),
    )
