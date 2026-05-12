from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    Conflict,
    Forbidden,
    InvalidStateTransition,
    NotFound,
)
from app.models import CheckIn, Feedback, Room, User
from app.models._enums import CheckInStatus, RoomStatus
from app.schemas.feedback import FeedbackCreate


async def submit_feedback(
    db: AsyncSession, user: User, room_id: UUID, body: FeedbackCreate
) -> Feedback:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.status not in (
        RoomStatus.IN_PROGRESS.value,
        RoomStatus.COMPLETED.value,
    ):
        raise InvalidStateTransition(
            "Feedback opens once the event is running or completed."
        )

    attended = await db.scalar(
        select(CheckIn).where(
            CheckIn.room_id == room_id,
            CheckIn.user_id == user.id,
            CheckIn.status == CheckInStatus.CHECKED_IN.value,
        )
    )
    if attended is None:
        raise Forbidden("Only checked-in attendees can submit feedback.")

    existing = await db.scalar(
        select(Feedback).where(
            Feedback.room_id == room_id, Feedback.user_id == user.id
        )
    )
    if existing is not None:
        raise Conflict(
            "FEEDBACK_ALREADY_SUBMITTED",
            "You have already submitted feedback for this room.",
        )

    fb = Feedback(
        room_id=room_id,
        user_id=user.id,
        rating=body.rating,
        comment=body.comment,
        safety_rating=body.safety_rating,
        planner_rating=body.planner_rating,
        would_join_again=body.would_join_again,
    )
    db.add(fb)
    await db.flush()
    return fb
