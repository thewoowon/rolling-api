import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIError, Forbidden, InvalidStateTransition, NotFound
from app.models import CheckIn, Planner, Profile, Room, RoomApplication, User
from app.models._enums import (
    ApplicationStatus,
    CheckInStatus,
    RoomStatus,
)


def _generate_code() -> str:
    return secrets.token_hex(3).upper()  # 6-char hex e.g. "A1B2C3"


async def _get_owned_room(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> Room:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.planner_id != planner.id:
        raise Forbidden("You do not own this room.")
    return room


async def open_checkin(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> list[CheckIn]:
    room = await _get_owned_room(db, planner, room_id)
    if room.status != RoomStatus.CONFIRMED.value:
        raise InvalidStateTransition(
            f"Check-in can only be opened on CONFIRMED rooms (was '{room.status}')."
        )

    # Confirmed applications drive check-in roster.
    confirmed_apps = (
        await db.scalars(
            select(RoomApplication).where(
                RoomApplication.room_id == room_id,
                RoomApplication.status == ApplicationStatus.CONFIRMED.value,
            )
        )
    ).all()
    if not confirmed_apps:
        raise APIError(
            "NO_CONFIRMED_PARTICIPANTS",
            "No confirmed participants to open check-in for.",
            status_code=409,
        )

    existing = (
        await db.scalars(select(CheckIn).where(CheckIn.room_id == room_id))
    ).all()
    existing_by_user = {c.user_id: c for c in existing}

    rows: list[CheckIn] = []
    for app in confirmed_apps:
        ck = existing_by_user.get(app.user_id)
        if ck is None:
            ck = CheckIn(
                room_id=room_id,
                user_id=app.user_id,
                application_id=app.id,
                status=CheckInStatus.OPEN.value,
                check_in_code=_generate_code(),
            )
            db.add(ck)
        else:
            if ck.status == CheckInStatus.NOT_OPEN.value:
                ck.status = CheckInStatus.OPEN.value
            if not ck.check_in_code:
                ck.check_in_code = _generate_code()
        rows.append(ck)
    await db.flush()
    return rows


async def list_room_checkins(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> list[tuple[CheckIn, Profile | None]]:
    await _get_owned_room(db, planner, room_id)
    rows = (
        await db.execute(
            select(CheckIn, Profile)
            .outerjoin(Profile, Profile.user_id == CheckIn.user_id)
            .where(CheckIn.room_id == room_id)
            .order_by(CheckIn.created_at.asc())
        )
    ).all()
    return [(c, p) for c, p in rows]


async def confirm_checkin_by_id(
    db: AsyncSession, planner: Planner, checkin_id: UUID
) -> CheckIn:
    ck = await db.scalar(select(CheckIn).where(CheckIn.id == checkin_id))
    if ck is None:
        raise NotFound("CHECKIN_NOT_FOUND", "Check-in not found.")
    room = await db.scalar(select(Room).where(Room.id == ck.room_id))
    if room is None or room.planner_id != planner.id:
        raise Forbidden("You do not own this room.")
    if ck.status not in (CheckInStatus.OPEN.value, CheckInStatus.NO_SHOW.value):
        raise InvalidStateTransition(
            f"Cannot mark CHECKED_IN from '{ck.status}'."
        )
    ck.status = CheckInStatus.CHECKED_IN.value
    ck.checked_in_at = datetime.now(timezone.utc)
    await db.flush()
    return ck


async def mark_no_show(
    db: AsyncSession, planner: Planner, checkin_id: UUID
) -> CheckIn:
    ck = await db.scalar(select(CheckIn).where(CheckIn.id == checkin_id))
    if ck is None:
        raise NotFound("CHECKIN_NOT_FOUND", "Check-in not found.")
    room = await db.scalar(select(Room).where(Room.id == ck.room_id))
    if room is None or room.planner_id != planner.id:
        raise Forbidden("You do not own this room.")
    if ck.status not in (CheckInStatus.OPEN.value, CheckInStatus.CHECKED_IN.value):
        raise InvalidStateTransition(
            f"Cannot mark NO_SHOW from '{ck.status}'."
        )
    ck.status = CheckInStatus.NO_SHOW.value
    await db.flush()
    return ck


async def get_my_checkin(db: AsyncSession, user: User, room_id: UUID) -> CheckIn:
    ck = await db.scalar(
        select(CheckIn).where(CheckIn.room_id == room_id, CheckIn.user_id == user.id)
    )
    if ck is None:
        raise NotFound(
            "CHECKIN_NOT_FOUND", "Check-in is not open for this room yet."
        )
    return ck
