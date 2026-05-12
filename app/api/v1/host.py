"""Host endpoints — any authenticated user can host a room."""
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import RoomApplication, User
from app.models._enums import ApplicationStatus
from app.schemas.application import (
    ApplicantBrief,
    ApplicationResponse,
    PlannerNoteUpdate,
)
from app.schemas.common import APIResponse
from app.schemas.host import HostRoomDetail, HostRoomItem
from app.schemas.room import RoomCreate, RoomUpdate
from app.services import audit_service, host_service

router = APIRouter()


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip() or ip
    return ip, ua


def _to_item(room) -> HostRoomItem:
    return HostRoomItem.model_validate(room)


@router.get("/rooms", response_model=APIResponse[list[HostRoomItem]])
async def list_my_rooms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[HostRoomItem]]:
    rooms = await host_service.list_my_rooms(db, user)
    return APIResponse(data=[_to_item(r) for r in rooms])


@router.post(
    "/rooms",
    response_model=APIResponse[HostRoomItem],
    status_code=status.HTTP_201_CREATED,
)
async def create_room(
    body: RoomCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[HostRoomItem]:
    room = await host_service.create_room(db, user, body)
    await db.commit()
    await db.refresh(room)
    return APIResponse(data=_to_item(room))


@router.get("/rooms/{room_id}", response_model=APIResponse[HostRoomDetail])
async def get_my_room(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[HostRoomDetail]:
    room = await host_service.get_my_room(db, user, room_id)
    summary = await host_service.get_capacity_summary(db, room.id, room)
    submitted = (
        await db.scalar(
            select(func.count())
            .select_from(RoomApplication)
            .where(
                RoomApplication.room_id == room.id,
                RoomApplication.status == ApplicationStatus.SUBMITTED.value,
            )
        )
    ) or 0
    confirmed = summary.male_confirmed + summary.female_confirmed
    detail = HostRoomDetail.model_validate(
        {
            **{c.name: getattr(room, c.name) for c in room.__table__.columns},
            "capacity_summary": summary,
            "viable_threshold": host_service.viable_threshold(room),
            "submitted_application_count": int(submitted),
            "confirmed_application_count": confirmed,
        }
    )
    return APIResponse(data=detail)


@router.put("/rooms/{room_id}", response_model=APIResponse[HostRoomItem])
async def update_my_room(
    room_id: UUID,
    body: RoomUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[HostRoomItem]:
    room = await host_service.update_room(db, user, room_id, body)
    await db.commit()
    await db.refresh(room)
    return APIResponse(data=_to_item(room))


@router.post("/rooms/{room_id}/publish", response_model=APIResponse[HostRoomItem])
async def publish_my_room(
    room_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[HostRoomItem]:
    room = await host_service.publish_room(db, user, room_id)
    ip, ua = _client_meta(request)
    await audit_service.log_action(
        db,
        actor=user,
        action="room.published",
        entity_type="room",
        entity_id=room.id,
        after={"status": room.status},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    await db.refresh(room)
    return APIResponse(data=_to_item(room))


@router.get(
    "/rooms/{room_id}/applications",
    response_model=APIResponse[list[ApplicantBrief]],
)
async def list_room_applications(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[ApplicantBrief]]:
    items = await host_service.list_room_applications(db, user, room_id)
    return APIResponse(data=items)


@router.post(
    "/applications/{application_id}/approve",
    response_model=APIResponse[ApplicationResponse],
)
async def approve_application(
    application_id: UUID,
    body: PlannerNoteUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ApplicationResponse]:
    app = await host_service.approve_application(db, user, application_id, body.planner_note)
    await db.commit()
    await db.refresh(app)
    return APIResponse(data=ApplicationResponse.model_validate(app))


@router.post(
    "/applications/{application_id}/reject",
    response_model=APIResponse[ApplicationResponse],
)
async def reject_application(
    application_id: UUID,
    body: PlannerNoteUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ApplicationResponse]:
    app = await host_service.reject_application(db, user, application_id, body.planner_note)
    await db.commit()
    await db.refresh(app)
    return APIResponse(data=ApplicationResponse.model_validate(app))


@router.post(
    "/applications/{application_id}/waitlist",
    response_model=APIResponse[ApplicationResponse],
)
async def waitlist_application(
    application_id: UUID,
    body: PlannerNoteUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ApplicationResponse]:
    app = await host_service.waitlist_application(db, user, application_id, body.planner_note)
    await db.commit()
    await db.refresh(app)
    return APIResponse(data=ApplicationResponse.model_validate(app))


@router.post(
    "/applications/{application_id}/mark-paid",
    response_model=APIResponse[ApplicationResponse],
)
async def mark_application_paid(
    application_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ApplicationResponse]:
    app = await host_service.mark_application_paid(db, user, application_id)
    ip, ua = _client_meta(request)
    await audit_service.log_action(
        db,
        actor=user,
        action="application.mark_paid",
        entity_type="room_application",
        entity_id=app.id,
        after={"status": app.status},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    await db.refresh(app)
    return APIResponse(data=ApplicationResponse.model_validate(app))
