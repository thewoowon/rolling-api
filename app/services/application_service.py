from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    APIError,
    Conflict,
    Forbidden,
    InvalidStateTransition,
    NotFound,
)
from app.models import Profile, Room, RoomApplication, User
from app.models._enums import ApplicationStatus, RoomStatus
from app.services import profile_service


APPLICATION_OPEN_STATUSES = (
    RoomStatus.PUBLISHED.value,
    RoomStatus.RECRUITING.value,
    RoomStatus.VIABLE.value,
    RoomStatus.ASSIGNED.value,
)


async def apply_to_room(
    db: AsyncSession,
    user: User,
    room_id: UUID,
    applicant_message: str | None,
) -> RoomApplication:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.status not in APPLICATION_OPEN_STATUSES:
        raise APIError(
            "ROOM_NOT_ACCEPTING_APPLICATIONS",
            "This room is not accepting applications right now.",
            status_code=409,
        )
    if room.application_deadline and datetime.now(timezone.utc) > room.application_deadline:
        raise APIError(
            "APPLICATION_DEADLINE_PASSED",
            "Application deadline has passed.",
            status_code=409,
        )

    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if not profile_service.is_profile_complete(profile):
        raise APIError(
            "PROFILE_INCOMPLETE",
            "Complete your profile before applying.",
            status_code=409,
        )

    existing = await db.scalar(
        select(RoomApplication).where(
            RoomApplication.room_id == room_id, RoomApplication.user_id == user.id
        )
    )
    if existing is not None and existing.status != ApplicationStatus.CANCELLED.value:
        raise Conflict("APPLICATION_ALREADY_EXISTS", "You have already applied to this room.")

    if existing is not None:
        # Reactivate a previously cancelled application.
        existing.status = ApplicationStatus.SUBMITTED.value
        existing.applicant_message = applicant_message
        existing.cancelled_at = None
        await db.flush()
        return existing

    application = RoomApplication(
        room_id=room_id,
        user_id=user.id,
        status=ApplicationStatus.SUBMITTED.value,
        applicant_message=applicant_message,
    )
    db.add(application)
    await db.flush()
    return application


async def cancel_my_application(
    db: AsyncSession, user: User, application_id: UUID
) -> RoomApplication:
    app = await db.scalar(
        select(RoomApplication).where(RoomApplication.id == application_id)
    )
    if app is None:
        raise NotFound("APPLICATION_NOT_FOUND", "Application not found.")
    if app.user_id != user.id:
        raise Forbidden("You can only cancel your own application.")

    cancellable_from = {
        ApplicationStatus.SUBMITTED.value,
        ApplicationStatus.WAITLISTED.value,
        ApplicationStatus.APPROVED.value,
        ApplicationStatus.PAYMENT_PENDING.value,
    }
    if app.status not in cancellable_from:
        raise InvalidStateTransition(
            f"Cannot cancel application in '{app.status}' state."
        )
    app.status = ApplicationStatus.CANCELLED.value
    app.cancelled_at = datetime.now(timezone.utc)
    await db.flush()
    return app


async def list_my_applications(
    db: AsyncSession, user: User
) -> list[RoomApplication]:
    return list(
        (
            await db.scalars(
                select(RoomApplication)
                .options(selectinload(RoomApplication.room))
                .where(RoomApplication.user_id == user.id)
                .order_by(RoomApplication.created_at.desc())
            )
        ).all()
    )


async def list_my_confirmed_rooms(db: AsyncSession, user: User) -> list[Room]:
    rows = (
        await db.execute(
            select(Room)
            .join(RoomApplication, RoomApplication.room_id == Room.id)
            .where(
                RoomApplication.user_id == user.id,
                RoomApplication.status == ApplicationStatus.CONFIRMED.value,
            )
            .order_by(Room.starts_at.asc())
        )
    ).scalars()
    return list(rows.all())
