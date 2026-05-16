from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFound
from app.models import Profile, Room, RoomApplication
from app.models._enums import (
    ApplicationStatus,
    Gender,
    RoomStatus,
    RoomType,
    RoomVisibility,
)
from app.schemas.room import (
    PlannerBrief,
    RoomCapacitySummary,
    RoomDetail,
    RoomListItem,
)

PUBLIC_VIEWABLE_STATUSES = (
    RoomStatus.PUBLISHED.value,
    RoomStatus.RECRUITING.value,
    RoomStatus.VIABLE.value,
    RoomStatus.ASSIGNED.value,
    RoomStatus.CONFIRMED.value,
    RoomStatus.IN_PROGRESS.value,
    RoomStatus.COMPLETED.value,
)

APPLICATION_OPEN_STATUSES = (
    RoomStatus.PUBLISHED.value,
    RoomStatus.RECRUITING.value,
    RoomStatus.VIABLE.value,
    RoomStatus.ASSIGNED.value,
)


async def list_public_rooms(
    db: AsyncSession,
    *,
    region: str | None,
    room_type: RoomType | None,
    starts_after: datetime | None,
    starts_before: datetime | None,
    min_age: int | None,
    max_age: int | None,
    limit: int,
    offset: int,
) -> tuple[list[Room], int]:
    base = select(Room).where(
        Room.visibility == RoomVisibility.PUBLIC.value,
        Room.status.in_(APPLICATION_OPEN_STATUSES),
    )
    if region:
        base = base.where(Room.region == region)
    if room_type:
        base = base.where(Room.room_type == room_type.value)
    if starts_after:
        base = base.where(Room.starts_at >= starts_after)
    if starts_before:
        base = base.where(Room.starts_at <= starts_before)
    if min_age is not None:
        base = base.where((Room.max_age.is_(None)) | (Room.max_age >= min_age))
    if max_age is not None:
        base = base.where((Room.min_age.is_(None)) | (Room.min_age <= max_age))

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    rooms_q = (
        base.options(selectinload(Room.planner))
        .order_by(Room.starts_at.asc())
        .limit(limit)
        .offset(offset)
    )
    rooms = list((await db.scalars(rooms_q)).all())
    return rooms, total


async def get_public_room(db: AsyncSession, room_id: UUID) -> Room:
    room = await db.scalar(
        select(Room).options(selectinload(Room.planner)).where(Room.id == room_id)
    )
    if room is None or room.status not in PUBLIC_VIEWABLE_STATUSES:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    return room


async def get_capacity_summary(
    db: AsyncSession, room_id: UUID, room: Room
) -> RoomCapacitySummary:
    confirmed_status = ApplicationStatus.CONFIRMED.value
    paid_status = ApplicationStatus.PAID.value

    male_case = case((Profile.gender == Gender.MALE.value, 1), else_=0)
    female_case = case((Profile.gender == Gender.FEMALE.value, 1), else_=0)

    row = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case((RoomApplication.status == confirmed_status, male_case), else_=0)
                    ),
                    0,
                ).label("male_confirmed"),
                func.coalesce(
                    func.sum(
                        case((RoomApplication.status == confirmed_status, female_case), else_=0)
                    ),
                    0,
                ).label("female_confirmed"),
                func.coalesce(
                    func.sum(case((RoomApplication.status == paid_status, male_case), else_=0)),
                    0,
                ).label("male_paid"),
                func.coalesce(
                    func.sum(
                        case((RoomApplication.status == paid_status, female_case), else_=0)
                    ),
                    0,
                ).label("female_paid"),
            )
            .select_from(RoomApplication)
            .join(Profile, Profile.user_id == RoomApplication.user_id)
            .where(RoomApplication.room_id == room_id)
        )
    ).one()

    return RoomCapacitySummary(
        male_capacity=room.male_capacity,
        female_capacity=room.female_capacity,
        male_confirmed=int(row.male_confirmed or 0),
        female_confirmed=int(row.female_confirmed or 0),
        male_paid=int(row.male_paid or 0),
        female_paid=int(row.female_paid or 0),
    )


def to_list_item(room: Room) -> RoomListItem:
    return RoomListItem.model_validate(
        {
            "id": room.id,
            "title": room.title,
            "subtitle": room.subtitle,
            "room_type": room.room_type,
            "status": room.status,
            "region": room.region,
            "starts_at": room.starts_at,
            "ends_at": room.ends_at,
            "min_age": room.min_age,
            "max_age": room.max_age,
            "price_amount": room.price_amount,
            "deposit_amount": room.deposit_amount,
            "currency": room.currency,
            "male_capacity": room.male_capacity,
            "female_capacity": room.female_capacity,
            "application_deadline": room.application_deadline,
            "planner": PlannerBrief.model_validate(room.planner) if room.planner else None,
        }
    )


def to_detail(room: Room, capacity: RoomCapacitySummary) -> RoomDetail:
    base = to_list_item(room).model_dump()
    base.update(
        {
            "description": room.description,
            "venue_name": room.venue_name,
            "venue_address": room.venue_address,
            "visibility": room.visibility,
            "capacity_summary": capacity,
        }
    )
    return RoomDetail.model_validate(base)
