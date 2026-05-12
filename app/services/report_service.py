from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIError, Forbidden, NotFound
from app.models import CheckIn, Report, Room, RoomApplication, User
from app.models._enums import ApplicationStatus, CheckInStatus, ReportStatus
from app.schemas.report import ReportCreate


async def submit_report(
    db: AsyncSession, user: User, body: ReportCreate
) -> Report:
    if body.reported_user_id is not None and body.reported_user_id == user.id:
        raise APIError(
            "INVALID_REPORT_TARGET",
            "You cannot report yourself.",
            status_code=409,
        )

    if body.room_id is not None:
        room = await db.scalar(select(Room).where(Room.id == body.room_id))
        if room is None:
            raise NotFound("ROOM_NOT_FOUND", "Room not found.")

        # Reporter must have a relationship with the room (applied or attended).
        attended = await db.scalar(
            select(CheckIn).where(
                CheckIn.room_id == body.room_id,
                CheckIn.user_id == user.id,
            )
        )
        applied = await db.scalar(
            select(RoomApplication).where(
                RoomApplication.room_id == body.room_id,
                RoomApplication.user_id == user.id,
            )
        )
        if attended is None and applied is None:
            raise Forbidden("You can only report a room you participated in.")

        if body.reported_user_id is not None:
            # Reported user should also be in the same room.
            other_attended = await db.scalar(
                select(CheckIn).where(
                    CheckIn.room_id == body.room_id,
                    CheckIn.user_id == body.reported_user_id,
                    CheckIn.status == CheckInStatus.CHECKED_IN.value,
                )
            )
            other_applied = await db.scalar(
                select(RoomApplication).where(
                    RoomApplication.room_id == body.room_id,
                    RoomApplication.user_id == body.reported_user_id,
                    RoomApplication.status.in_(
                        (
                            ApplicationStatus.CONFIRMED.value,
                            ApplicationStatus.PAID.value,
                            ApplicationStatus.APPROVED.value,
                        )
                    ),
                )
            )
            if other_attended is None and other_applied is None:
                raise APIError(
                    "INVALID_REPORT_TARGET",
                    "Reported user is not part of this room.",
                    status_code=409,
                )

    report = Report(
        reporter_id=user.id,
        reported_user_id=body.reported_user_id,
        room_id=body.room_id,
        reason=body.reason,
        description=body.description,
        status=ReportStatus.OPEN.value,
    )
    db.add(report)
    await db.flush()
    return report
