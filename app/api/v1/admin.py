from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_roles
from app.models import User
from app.models._enums import (
    PaymentStatus,
    PlannerStatus,
    ReportStatus,
    RoomStatus,
    UserRole,
    UserStatus,
)
from app.schemas.admin import (
    AdminAssignRequest,
    AdminDashboard,
    AdminPaymentItem,
    AdminPlannerItem,
    AdminQueueItem,
    AdminReportItem,
    AdminReportResolution,
    AdminRoomItem,
    AdminUserItem,
)
from app.schemas.common import APIResponse
from app.services import admin_service

router = APIRouter()
AdminUser = Depends(require_roles(UserRole.ADMIN))


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip() or ip
    return ip, ua


@router.get("/dashboard", response_model=APIResponse[AdminDashboard])
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _user: User = AdminUser,
) -> APIResponse[AdminDashboard]:
    return APIResponse(data=await admin_service.dashboard(db))


@router.get("/users", response_model=APIResponse[list[AdminUserItem]])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _user: User = AdminUser,
    role: UserRole | None = Query(default=None),
    status: UserStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[list[AdminUserItem]]:
    return APIResponse(
        data=await admin_service.list_users(
            db, role=role, status=status, limit=limit, offset=offset
        )
    )


@router.post("/users/{user_id}/block", response_model=APIResponse[AdminUserItem])
async def block_user(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = AdminUser,
) -> APIResponse[AdminUserItem]:
    ip, ua = _client_meta(request)
    u = await admin_service.set_user_status(db, user, user_id, UserStatus.BLOCKED, ip, ua)
    await db.commit()
    items = await admin_service.list_users(db, limit=1, offset=0)
    found = next((x for x in items if x.id == u.id), None)
    return APIResponse(data=found or items[0])


@router.post("/users/{user_id}/unblock", response_model=APIResponse[AdminUserItem])
async def unblock_user(
    user_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = AdminUser,
) -> APIResponse[AdminUserItem]:
    ip, ua = _client_meta(request)
    u = await admin_service.set_user_status(db, user, user_id, UserStatus.ACTIVE, ip, ua)
    await db.commit()
    return APIResponse(
        data=AdminUserItem.model_validate(
            {
                "id": u.id,
                "email": u.email,
                "phone": u.phone,
                "role": u.role,
                "status": u.status,
                "last_login_at": u.last_login_at,
                "created_at": u.created_at,
                "display_name": None,
            }
        )
    )


@router.get("/planners", response_model=APIResponse[list[AdminPlannerItem]])
async def list_planners(
    db: AsyncSession = Depends(get_db),
    _user: User = AdminUser,
    status: PlannerStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[list[AdminPlannerItem]]:
    return APIResponse(
        data=await admin_service.list_planners(
            db, status=status, limit=limit, offset=offset
        )
    )


@router.post(
    "/planners/{planner_id}/approve", response_model=APIResponse[AdminPlannerItem]
)
async def approve_planner(
    planner_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = AdminUser,
) -> APIResponse[AdminPlannerItem]:
    ip, ua = _client_meta(request)
    p = await admin_service.set_planner_status(
        db, user, planner_id, PlannerStatus.APPROVED, ip, ua
    )
    await db.commit()
    items = await admin_service.list_planners(db, limit=200)
    found = next((x for x in items if x.id == p.id), None)
    return APIResponse(data=found or items[0])


@router.post(
    "/planners/{planner_id}/suspend", response_model=APIResponse[AdminPlannerItem]
)
async def suspend_planner(
    planner_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = AdminUser,
) -> APIResponse[AdminPlannerItem]:
    ip, ua = _client_meta(request)
    p = await admin_service.set_planner_status(
        db, user, planner_id, PlannerStatus.SUSPENDED, ip, ua
    )
    await db.commit()
    items = await admin_service.list_planners(db, limit=200)
    found = next((x for x in items if x.id == p.id), None)
    return APIResponse(data=found or items[0])


@router.get("/rooms", response_model=APIResponse[list[AdminRoomItem]])
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    _user: User = AdminUser,
    status: RoomStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[list[AdminRoomItem]]:
    return APIResponse(
        data=await admin_service.list_rooms(
            db, status=status, limit=limit, offset=offset
        )
    )


@router.get("/payments", response_model=APIResponse[list[AdminPaymentItem]])
async def list_payments(
    db: AsyncSession = Depends(get_db),
    _user: User = AdminUser,
    status: PaymentStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[list[AdminPaymentItem]]:
    return APIResponse(
        data=await admin_service.list_payments(
            db, status=status, limit=limit, offset=offset
        )
    )


@router.get("/reports", response_model=APIResponse[list[AdminReportItem]])
async def list_reports(
    db: AsyncSession = Depends(get_db),
    _user: User = AdminUser,
    status: ReportStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[list[AdminReportItem]]:
    return APIResponse(
        data=await admin_service.list_reports(
            db, status=status, limit=limit, offset=offset
        )
    )


@router.get("/queue", response_model=APIResponse[list[AdminQueueItem]])
async def list_queue(
    db: AsyncSession = Depends(get_db),
    _user: User = AdminUser,
    include_assigned: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[list[AdminQueueItem]]:
    return APIResponse(
        data=await admin_service.list_queue(
            db,
            include_assigned=include_assigned,
            limit=limit,
            offset=offset,
        )
    )


@router.post("/queue/{room_id}/assign", response_model=APIResponse[AdminQueueItem])
async def assign_planner(
    room_id: UUID,
    body: AdminAssignRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = AdminUser,
) -> APIResponse[AdminQueueItem]:
    ip, ua = _client_meta(request)
    await admin_service.assign_planner_to_room(
        db, user, room_id, body.planner_id, ip, ua
    )
    await db.commit()
    rows = await admin_service.list_queue(db, include_assigned=True, limit=200)
    found = next((x for x in rows if x.id == room_id), None)
    if found is None:
        # Fall back to a non-queue row read; unlikely path.
        raise admin_service.NotFound("ROOM_NOT_FOUND", "Room not found.")  # type: ignore[attr-defined]
    return APIResponse(data=found)


@router.post(
    "/reports/{report_id}/resolve", response_model=APIResponse[AdminReportItem]
)
async def resolve_report(
    report_id: UUID,
    request: Request,
    body: AdminReportResolution,
    db: AsyncSession = Depends(get_db),
    user: User = AdminUser,
) -> APIResponse[AdminReportItem]:
    ip, ua = _client_meta(request)
    await admin_service.set_report_status(
        db, user, report_id, ReportStatus.RESOLVED, ip, ua, note=body.note
    )
    await db.commit()
    rows = await admin_service.list_reports(db, limit=200)
    found = next((x for x in rows if x.id == report_id), None)
    return APIResponse(data=found or rows[0])


@router.post(
    "/reports/{report_id}/dismiss", response_model=APIResponse[AdminReportItem]
)
async def dismiss_report(
    report_id: UUID,
    request: Request,
    body: AdminReportResolution,
    db: AsyncSession = Depends(get_db),
    user: User = AdminUser,
) -> APIResponse[AdminReportItem]:
    ip, ua = _client_meta(request)
    await admin_service.set_report_status(
        db, user, report_id, ReportStatus.DISMISSED, ip, ua, note=body.note
    )
    await db.commit()
    rows = await admin_service.list_reports(db, limit=200)
    found = next((x for x in rows if x.id == report_id), None)
    return APIResponse(data=found or rows[0])
