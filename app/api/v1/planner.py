"""Planner endpoints — Rolling-affiliated operators run rooms assigned to them
from the admin queue. Room creation/recruitment now lives under /host.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_roles
from app.models import User
from app.models._enums import UserRole
from app.schemas.checkin import CheckInPlannerItem
from app.schemas.common import APIResponse
from app.schemas.planner import (
    PlannerDashboard,
    PlannerRoomDetail,
    PlannerRoomItem,
)
from app.schemas.rotation import RotationSessionView, RotationStartRequest
from app.services import (
    audit_service,
    checkin_service,
    planner_service,
    rotation_service,
)

router = APIRouter()
PlannerUser = Depends(require_roles(UserRole.PLANNER))


def _planner_room_item(room) -> PlannerRoomItem:
    return PlannerRoomItem.model_validate(room)


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip() or ip
    return ip, ua


@router.get("/dashboard", response_model=APIResponse[PlannerDashboard])
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[PlannerDashboard]:
    planner = await planner_service.get_planner_for_user(db, user)
    counts = await planner_service.dashboard_counts(db, planner)
    return APIResponse(data=counts)


@router.get("/assigned", response_model=APIResponse[list[PlannerRoomItem]])
async def list_assigned(
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[list[PlannerRoomItem]]:
    planner = await planner_service.get_planner_for_user(db, user)
    rooms = await planner_service.list_assigned_rooms(db, planner)
    return APIResponse(data=[_planner_room_item(r) for r in rooms])


@router.get("/rooms/{room_id}", response_model=APIResponse[PlannerRoomDetail])
async def get_assigned_room(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[PlannerRoomDetail]:
    planner = await planner_service.get_planner_for_user(db, user)
    room = await planner_service.get_assigned_room(db, planner, room_id)
    summary, confirmed, submitted = await planner_service.get_room_summary_counts(db, room)
    detail = PlannerRoomDetail.model_validate(
        {
            **{c.name: getattr(room, c.name) for c in room.__table__.columns},
            "capacity_summary": summary,
            "pending_application_count": confirmed,
            "submitted_application_count": submitted,
        }
    )
    return APIResponse(data=detail)


@router.post("/rooms/{room_id}/confirm", response_model=APIResponse[PlannerRoomItem])
async def confirm_assigned_room(
    room_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[PlannerRoomItem]:
    planner = await planner_service.get_planner_for_user(db, user)
    room = await planner_service.confirm_room(db, planner, room_id)
    ip, ua = _client_meta(request)
    await audit_service.log_action(
        db,
        actor=user,
        action="room.confirmed",
        entity_type="room",
        entity_id=room.id,
        after={"status": room.status},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    await db.refresh(room)
    return APIResponse(data=_planner_room_item(room))


# ---- Check-in management -------------------------------------------------


def _checkin_item(ck, profile) -> CheckInPlannerItem:
    return CheckInPlannerItem.model_validate(
        {
            "id": ck.id,
            "user_id": ck.user_id,
            "application_id": ck.application_id,
            "status": ck.status,
            "checked_in_at": ck.checked_in_at,
            "check_in_code": ck.check_in_code,
            "display_name": profile.display_name if profile else None,
            "gender": profile.gender if profile else None,
            "birth_year": profile.birth_year if profile else None,
            "region": profile.region if profile else None,
        }
    )


@router.post(
    "/rooms/{room_id}/checkins/open",
    response_model=APIResponse[list[CheckInPlannerItem]],
)
async def open_room_checkin(
    room_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[list[CheckInPlannerItem]]:
    planner = await planner_service.get_planner_for_user(db, user)
    await planner_service.get_assigned_room(db, planner, room_id)
    checkins = await checkin_service.open_checkin(db, planner, room_id)
    ip, ua = _client_meta(request)
    await audit_service.log_action(
        db,
        actor=user,
        action="checkin.opened",
        entity_type="room",
        entity_id=room_id,
        after={"count": len(checkins)},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    rows = await checkin_service.list_room_checkins(db, planner, room_id)
    return APIResponse(data=[_checkin_item(c, p) for c, p in rows])


@router.get(
    "/rooms/{room_id}/checkins",
    response_model=APIResponse[list[CheckInPlannerItem]],
)
async def list_room_checkins(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[list[CheckInPlannerItem]]:
    planner = await planner_service.get_planner_for_user(db, user)
    await planner_service.get_assigned_room(db, planner, room_id)
    rows = await checkin_service.list_room_checkins(db, planner, room_id)
    return APIResponse(data=[_checkin_item(c, p) for c, p in rows])


@router.post(
    "/checkins/{checkin_id}/confirm",
    response_model=APIResponse[CheckInPlannerItem],
)
async def confirm_checkin(
    checkin_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[CheckInPlannerItem]:
    planner = await planner_service.get_planner_for_user(db, user)
    ck = await checkin_service.confirm_checkin_by_id(db, planner, checkin_id)
    await db.commit()
    await db.refresh(ck)
    from sqlalchemy import select

    from app.models import Profile

    profile = await db.scalar(select(Profile).where(Profile.user_id == ck.user_id))
    return APIResponse(data=_checkin_item(ck, profile))


@router.post(
    "/checkins/{checkin_id}/no-show",
    response_model=APIResponse[CheckInPlannerItem],
)
async def mark_checkin_no_show(
    checkin_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[CheckInPlannerItem]:
    planner = await planner_service.get_planner_for_user(db, user)
    ck = await checkin_service.mark_no_show(db, planner, checkin_id)
    await db.commit()
    await db.refresh(ck)
    from sqlalchemy import select

    from app.models import Profile

    profile = await db.scalar(select(Profile).where(Profile.user_id == ck.user_id))
    return APIResponse(data=_checkin_item(ck, profile))


# ---- Rotation control ----------------------------------------------------


@router.post(
    "/rooms/{room_id}/rotation/start",
    response_model=APIResponse[RotationSessionView],
)
async def start_rotation(
    room_id: UUID,
    body: RotationStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[RotationSessionView]:
    planner = await planner_service.get_planner_for_user(db, user)
    session = await rotation_service.start_session(
        db, planner, room_id, round_duration_minutes=body.round_duration_minutes
    )
    ip, ua = _client_meta(request)
    await audit_service.log_action(
        db,
        actor=user,
        action="rotation.started",
        entity_type="rotation_session",
        entity_id=session.id,
        after={"round_duration_minutes": body.round_duration_minutes},
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    view = await rotation_service.get_session_view(db, planner, room_id)
    return APIResponse(data=view)


@router.post(
    "/rooms/{room_id}/rotation/next",
    response_model=APIResponse[RotationSessionView],
)
async def advance_rotation(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[RotationSessionView]:
    planner = await planner_service.get_planner_for_user(db, user)
    await rotation_service.next_round(db, planner, room_id)
    await db.commit()
    view = await rotation_service.get_session_view(db, planner, room_id)
    return APIResponse(data=view)


@router.post(
    "/rooms/{room_id}/rotation/end",
    response_model=APIResponse[RotationSessionView],
)
async def finish_rotation(
    room_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[RotationSessionView]:
    planner = await planner_service.get_planner_for_user(db, user)
    session = await rotation_service.end_session(db, planner, room_id)
    ip, ua = _client_meta(request)
    await audit_service.log_action(
        db,
        actor=user,
        action="rotation.completed",
        entity_type="rotation_session",
        entity_id=session.id,
        ip_address=ip,
        user_agent=ua,
    )
    await db.commit()
    view = await rotation_service.get_session_view(db, planner, room_id)
    return APIResponse(data=view)


@router.get(
    "/rooms/{room_id}/rotation",
    response_model=APIResponse[RotationSessionView],
)
async def get_rotation(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = PlannerUser,
) -> APIResponse[RotationSessionView]:
    planner = await planner_service.get_planner_for_user(db, user)
    view = await rotation_service.get_session_view(db, planner, room_id)
    return APIResponse(data=view)
