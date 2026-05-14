"""Host = the user who creates and owns a room.

Hosts (any authenticated user) can:
- Create/edit/publish rooms
- Approve/reject/mark-paid applications to their own room
- See room progress toward viability

After a room reaches VIABLE, an internal Planner is assigned by an admin and
takes over event operations (check-in, rotation).
"""
from datetime import datetime, timezone
from math import ceil
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    APIError,
    Forbidden,
    InvalidStateTransition,
    NotFound,
)
from app.models import Profile, Room, RoomApplication, User
from app.models._enums import (
    ApplicationStatus,
    Gender,
    RoomStatus,
    UserStatus,
)
from app.schemas.application import ApplicantBrief
from app.schemas.room import RoomCapacitySummary, RoomCreate, RoomUpdate
from app.services import credit_service


HOST_EDITABLE_STATES = (
    RoomStatus.DRAFT.value,
    RoomStatus.PUBLISHED.value,
    RoomStatus.RECRUITING.value,
)
HOST_PUBLISH_FROM = (RoomStatus.DRAFT.value,)
APPLICATION_MGMT_STATES = (
    RoomStatus.PUBLISHED.value,
    RoomStatus.RECRUITING.value,
    RoomStatus.VIABLE.value,
    RoomStatus.ASSIGNED.value,
)


def _is_active(user: User) -> bool:
    return user.status == UserStatus.ACTIVE.value


async def _get_owned_room(db: AsyncSession, user: User, room_id: UUID) -> Room:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.host_user_id != user.id:
        raise Forbidden("You are not the host of this room.")
    return room


async def list_my_rooms(db: AsyncSession, user: User) -> list[Room]:
    rows = await db.scalars(
        select(Room).where(Room.host_user_id == user.id).order_by(Room.starts_at.desc())
    )
    return list(rows.all())


async def create_room(db: AsyncSession, user: User, body: RoomCreate) -> Room:
    if not _is_active(user):
        raise Forbidden(f"Account is {user.status}.")
    room = Room(
        host_user_id=user.id,
        planner_id=None,
        title=body.title,
        subtitle=body.subtitle,
        description=body.description,
        room_type=body.room_type.value,
        status=RoomStatus.DRAFT.value,
        region=body.region,
        venue_name=body.venue_name,
        venue_address=body.venue_address,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        min_age=body.min_age,
        max_age=body.max_age,
        male_capacity=body.male_capacity,
        female_capacity=body.female_capacity,
        price_amount=body.price_amount,
        deposit_amount=body.deposit_amount,
        currency=body.currency,
        application_deadline=body.application_deadline,
        visibility=body.visibility.value,
        payment_instructions=body.payment_instructions,
    )
    db.add(room)
    await db.flush()
    return room


async def get_my_room(db: AsyncSession, user: User, room_id: UUID) -> Room:
    return await _get_owned_room(db, user, room_id)


async def update_room(
    db: AsyncSession, user: User, room_id: UUID, body: RoomUpdate
) -> Room:
    room = await _get_owned_room(db, user, room_id)
    if room.status not in HOST_EDITABLE_STATES:
        raise InvalidStateTransition(
            f"Cannot edit room in '{room.status}' state."
        )
    payload = body.model_dump(exclude_unset=True)
    if "visibility" in payload and payload["visibility"] is not None:
        payload["visibility"] = payload["visibility"].value
    for k, v in payload.items():
        if v is None and k in {"title", "region"}:
            continue
        setattr(room, k, v)
    if room.ends_at <= room.starts_at:
        raise APIError("VALIDATION_ERROR", "ends_at must be after starts_at", status_code=422)
    await db.flush()
    return room


async def publish_room(db: AsyncSession, user: User, room_id: UUID) -> Room:
    room = await _get_owned_room(db, user, room_id)
    if room.status not in HOST_PUBLISH_FROM:
        raise InvalidStateTransition(
            f"Only DRAFT rooms can be published (was '{room.status}')."
        )
    room.status = RoomStatus.PUBLISHED.value
    await db.flush()
    return room


# ---- Application management (host = curator before VIABLE) -------------


async def _get_owned_application(
    db: AsyncSession, user: User, application_id: UUID
) -> RoomApplication:
    app = await db.scalar(
        select(RoomApplication).where(RoomApplication.id == application_id)
    )
    if app is None:
        raise NotFound("APPLICATION_NOT_FOUND", "Application not found.")
    room = await db.scalar(select(Room).where(Room.id == app.room_id))
    if room is None or room.host_user_id != user.id:
        raise Forbidden("You are not the host of this room.")
    return app


async def list_room_applications(
    db: AsyncSession, user: User, room_id: UUID
) -> list[ApplicantBrief]:
    await _get_owned_room(db, user, room_id)
    rows = (
        await db.execute(
            select(RoomApplication, Profile)
            .outerjoin(Profile, Profile.user_id == RoomApplication.user_id)
            .where(RoomApplication.room_id == room_id)
            .order_by(RoomApplication.created_at.desc())
        )
    ).all()
    items: list[ApplicantBrief] = []
    for app, profile in rows:
        items.append(
            ApplicantBrief.model_validate(
                {
                    "id": app.id,
                    "user_id": app.user_id,
                    "status": app.status,
                    "applicant_message": app.applicant_message,
                    "planner_note": app.planner_note,
                    "created_at": app.created_at,
                    "display_name": profile.display_name if profile else None,
                    "gender": profile.gender if profile else None,
                    "birth_year": profile.birth_year if profile else None,
                    "region": profile.region if profile else None,
                    "job_title": profile.job_title if profile else None,
                    "intro": profile.intro if profile else None,
                    "profile_image_url": profile.profile_image_url if profile else None,
                }
            )
        )
    return items


async def approve_application(
    db: AsyncSession, user: User, application_id: UUID, note: str | None
) -> RoomApplication:
    app = await _get_owned_application(db, user, application_id)
    if app.status not in (
        ApplicationStatus.SUBMITTED.value,
        ApplicationStatus.WAITLISTED.value,
    ):
        raise InvalidStateTransition(
            f"Cannot approve application in '{app.status}' state."
        )
    app.status = ApplicationStatus.APPROVED.value
    app.approved_at = datetime.now(timezone.utc)
    if note is not None:
        app.planner_note = note
    await db.flush()
    return app


async def reject_application(
    db: AsyncSession, user: User, application_id: UUID, note: str | None
) -> RoomApplication:
    app = await _get_owned_application(db, user, application_id)
    if app.status not in (
        ApplicationStatus.SUBMITTED.value,
        ApplicationStatus.WAITLISTED.value,
        ApplicationStatus.APPROVED.value,
        ApplicationStatus.PAYMENT_PENDING.value,
    ):
        raise InvalidStateTransition(
            f"Cannot reject application in '{app.status}' state."
        )
    app.status = ApplicationStatus.REJECTED.value
    app.rejected_at = datetime.now(timezone.utc)
    if note is not None:
        app.planner_note = note
    await db.flush()
    return app


async def waitlist_application(
    db: AsyncSession, user: User, application_id: UUID, note: str | None
) -> RoomApplication:
    app = await _get_owned_application(db, user, application_id)
    if app.status != ApplicationStatus.SUBMITTED.value:
        raise InvalidStateTransition(
            f"Only SUBMITTED applications can be waitlisted (was '{app.status}')."
        )
    app.status = ApplicationStatus.WAITLISTED.value
    if note is not None:
        app.planner_note = note
    await db.flush()
    return app


async def mark_application_paid(
    db: AsyncSession, user: User, application_id: UUID
) -> RoomApplication:
    """MVP manual override: host marks payment confirmed -> CONFIRMED.

    After this, the room is re-evaluated for VIABLE state.
    """
    app = await _get_owned_application(db, user, application_id)
    if app.status not in (
        ApplicationStatus.APPROVED.value,
        ApplicationStatus.PAYMENT_PENDING.value,
        ApplicationStatus.PAID.value,
    ):
        raise InvalidStateTransition(
            f"Cannot mark application as paid in '{app.status}' state."
        )
    app.status = ApplicationStatus.CONFIRMED.value
    await db.flush()
    # 1) Re-check whether this confirmation pushes the room into VIABLE.
    await maybe_promote_to_viable(db, app.room_id)
    # 2) If this is the applicant's FIRST CONFIRMED room and they were referred,
    #    award the referral pair (idempotent — emitter flag flips).
    await _maybe_emit_referral_bonus(db, app.user_id)
    return app


async def _maybe_emit_referral_bonus(db: AsyncSession, applicant_user_id: UUID) -> None:
    """Award referrer + applicant the referral credit pair on FIRST confirmed app."""
    applicant = await db.scalar(select(User).where(User.id == applicant_user_id))
    if applicant is None or applicant.referred_by_user_id is None:
        return
    if applicant.referral_bonus_emitted:
        return
    await credit_service.issue_referral_pair(
        db, referrer_id=applicant.referred_by_user_id, friend_id=applicant.id
    )
    applicant.referral_bonus_emitted = True
    await db.flush()


# ---- Capacity + viability ----------------------------------------------


def _viable_threshold_male(room: Room) -> int:
    return max(1, ceil(room.male_capacity * 0.5))


def _viable_threshold_female(room: Room) -> int:
    return max(1, ceil(room.female_capacity * 0.5))


def _viable_threshold(room: Room) -> int:
    """Total threshold (for display). Both genders must independently hit half."""
    return _viable_threshold_male(room) + _viable_threshold_female(room)


async def get_capacity_summary(
    db: AsyncSession, room_id: UUID, room: Room
) -> RoomCapacitySummary:
    confirmed = ApplicationStatus.CONFIRMED.value
    paid = ApplicationStatus.PAID.value
    male_case = case((Profile.gender == Gender.MALE.value, 1), else_=0)
    female_case = case((Profile.gender == Gender.FEMALE.value, 1), else_=0)
    row = (
        await db.execute(
            select(
                func.coalesce(
                    func.sum(case((RoomApplication.status == confirmed, male_case), else_=0)), 0
                ).label("mc"),
                func.coalesce(
                    func.sum(case((RoomApplication.status == confirmed, female_case), else_=0)),
                    0,
                ).label("fc"),
                func.coalesce(
                    func.sum(case((RoomApplication.status == paid, male_case), else_=0)), 0
                ).label("mp"),
                func.coalesce(
                    func.sum(case((RoomApplication.status == paid, female_case), else_=0)), 0
                ).label("fp"),
            )
            .select_from(RoomApplication)
            .join(Profile, Profile.user_id == RoomApplication.user_id)
            .where(RoomApplication.room_id == room_id)
        )
    ).one()
    return RoomCapacitySummary(
        male_capacity=room.male_capacity,
        female_capacity=room.female_capacity,
        male_confirmed=int(row.mc or 0),
        female_confirmed=int(row.fc or 0),
        male_paid=int(row.mp or 0),
        female_paid=int(row.fp or 0),
    )


async def maybe_promote_to_viable(db: AsyncSession, room_id: UUID) -> bool:
    """If a PUBLISHED/RECRUITING room has hit the viability threshold,
    promote it to VIABLE and enqueue for admin assignment. Idempotent.
    Returns True if promoted in this call.
    """
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        return False
    if room.status not in (RoomStatus.PUBLISHED.value, RoomStatus.RECRUITING.value):
        return False
    summary = await get_capacity_summary(db, room_id, room)
    if summary.male_confirmed < _viable_threshold_male(room):
        return False
    if summary.female_confirmed < _viable_threshold_female(room):
        return False
    room.status = RoomStatus.VIABLE.value
    room.viable_at = datetime.now(timezone.utc)
    await db.flush()
    # Reward the host with a percentage-off coupon (idempotent).
    await credit_service.issue_viable_host_bonus(
        db, host_user_id=room.host_user_id, room_id=room.id
    )
    return True


def viable_threshold(room: Room) -> int:
    return _viable_threshold(room)
