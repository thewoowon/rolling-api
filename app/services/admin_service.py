from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import APIError, InvalidStateTransition, NotFound
from app.models import (
    Payment,
    Planner,
    Profile,
    Report,
    Room,
    User,
)
from app.models._enums import (
    PaymentStatus,
    PlannerStatus,
    ReportStatus,
    RoomStatus,
    UserRole,
    UserStatus,
)
from app.schemas.admin import (
    AdminDashboard,
    AdminPaymentItem,
    AdminPlannerItem,
    AdminQueueItem,
    AdminReportItem,
    AdminRoomItem,
    AdminUserItem,
)
from app.services import audit_service, host_service


async def dashboard(db: AsyncSession) -> AdminDashboard:
    total_users = (await db.scalar(select(func.count()).select_from(User))) or 0
    active_users = (
        await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.status == UserStatus.ACTIVE.value)
        )
    ) or 0
    blocked_users = (
        await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.status == UserStatus.BLOCKED.value)
        )
    ) or 0
    total_planners = (await db.scalar(select(func.count()).select_from(Planner))) or 0
    pending_planners = (
        await db.scalar(
            select(func.count())
            .select_from(Planner)
            .where(Planner.status == PlannerStatus.PENDING.value)
        )
    ) or 0

    rows = (
        await db.execute(
            select(Room.status, func.count()).select_from(Room).group_by(Room.status)
        )
    ).all()
    rooms_by_status = {status: int(count) for status, count in rows}

    open_reports = (
        await db.scalar(
            select(func.count())
            .select_from(Report)
            .where(Report.status == ReportStatus.OPEN.value)
        )
    ) or 0
    paid_payments = (
        await db.scalar(
            select(func.count())
            .select_from(Payment)
            .where(Payment.status == PaymentStatus.PAID.value)
        )
    ) or 0

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    completed_recent = (
        await db.scalar(
            select(func.count())
            .select_from(Room)
            .where(
                Room.status == RoomStatus.COMPLETED.value,
                Room.updated_at >= thirty_days_ago,
            )
        )
    ) or 0

    return AdminDashboard(
        total_users=int(total_users),
        active_users=int(active_users),
        blocked_users=int(blocked_users),
        total_planners=int(total_planners),
        pending_planners=int(pending_planners),
        rooms_by_status=rooms_by_status,
        open_reports=int(open_reports),
        paid_payments=int(paid_payments),
        completed_rooms_last_30d=int(completed_recent),
    )


async def list_users(
    db: AsyncSession,
    *,
    role: UserRole | None = None,
    status: UserStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminUserItem]:
    q = select(User, Profile).outerjoin(Profile, Profile.user_id == User.id)
    if role:
        q = q.where(User.role == role.value)
    if status:
        q = q.where(User.status == status.value)
    q = q.order_by(User.created_at.desc()).limit(limit).offset(offset)

    rows = (await db.execute(q)).all()
    out: list[AdminUserItem] = []
    for u, p in rows:
        out.append(
            AdminUserItem.model_validate(
                {
                    "id": u.id,
                    "email": u.email,
                    "phone": u.phone,
                    "role": u.role,
                    "status": u.status,
                    "last_login_at": u.last_login_at,
                    "created_at": u.created_at,
                    "display_name": p.display_name if p else None,
                }
            )
        )
    return out


async def set_user_status(
    db: AsyncSession,
    actor: User,
    user_id: UUID,
    new_status: UserStatus,
    ip: str | None,
    ua: str | None,
) -> User:
    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise NotFound("USER_NOT_FOUND", "User not found.")
    if user.id == actor.id:
        raise APIError("INVALID_TARGET", "Cannot change your own status.", status_code=409)
    before = {"status": user.status}
    user.status = new_status.value
    await db.flush()
    await audit_service.log_action(
        db,
        actor=actor,
        action=f"user.{new_status.value}",
        entity_type="user",
        entity_id=user.id,
        before=before,
        after={"status": user.status},
        ip_address=ip,
        user_agent=ua,
    )
    return user


async def list_planners(
    db: AsyncSession,
    *,
    status: PlannerStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminPlannerItem]:
    q = select(Planner, User).join(User, User.id == Planner.user_id)
    if status:
        q = q.where(Planner.status == status.value)
    q = q.order_by(Planner.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(q)).all()
    return [
        AdminPlannerItem.model_validate(
            {
                "id": p.id,
                "user_id": p.user_id,
                "user_email": u.email,
                "name": p.name,
                "bio": p.bio,
                "region": p.region,
                "status": p.status,
                "rating": float(p.rating) if p.rating is not None else None,
                "total_rooms": p.total_rooms,
                "created_at": p.created_at,
            }
        )
        for p, u in rows
    ]


async def set_planner_status(
    db: AsyncSession,
    actor: User,
    planner_id: UUID,
    new_status: PlannerStatus,
    ip: str | None,
    ua: str | None,
) -> Planner:
    planner = await db.scalar(select(Planner).where(Planner.id == planner_id))
    if planner is None:
        raise NotFound("PLANNER_NOT_FOUND", "Planner not found.")
    before = {"status": planner.status}
    planner.status = new_status.value
    await db.flush()
    await audit_service.log_action(
        db,
        actor=actor,
        action=f"planner.{new_status.value}",
        entity_type="planner",
        entity_id=planner.id,
        before=before,
        after={"status": planner.status},
        ip_address=ip,
        user_agent=ua,
    )
    return planner


async def list_rooms(
    db: AsyncSession,
    *,
    status: RoomStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminRoomItem]:
    q = select(Room, Planner).join(Planner, Planner.id == Room.planner_id)
    if status:
        q = q.where(Room.status == status.value)
    q = q.order_by(Room.starts_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(q)).all()
    return [
        AdminRoomItem.model_validate(
            {
                "id": r.id,
                "title": r.title,
                "status": r.status,
                "room_type": r.room_type,
                "region": r.region,
                "starts_at": r.starts_at,
                "ends_at": r.ends_at,
                "male_capacity": r.male_capacity,
                "female_capacity": r.female_capacity,
                "price_amount": r.price_amount,
                "deposit_amount": r.deposit_amount,
                "planner_id": r.planner_id,
                "planner_name": p.name if p else None,
            }
        )
        for r, p in rows
    ]


async def list_payments(
    db: AsyncSession,
    *,
    status: PaymentStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminPaymentItem]:
    q = select(Payment)
    if status:
        q = q.where(Payment.status == status.value)
    q = q.order_by(Payment.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.scalars(q)).all()
    return [AdminPaymentItem.model_validate(p) for p in rows]


async def list_reports(
    db: AsyncSession,
    *,
    status: ReportStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminReportItem]:
    reporter_u = User.__table__.alias("reporter_u")
    reported_u = User.__table__.alias("reported_u")
    q = (
        select(
            Report,
            reporter_u.c.email.label("reporter_email"),
            reported_u.c.email.label("reported_email"),
        )
        .join(reporter_u, reporter_u.c.id == Report.reporter_id, isouter=False)
        .join(
            reported_u, reported_u.c.id == Report.reported_user_id, isouter=True
        )
    )
    if status:
        q = q.where(Report.status == status.value)
    q = q.order_by(Report.created_at.desc()).limit(limit).offset(offset)
    rows = (await db.execute(q)).all()
    return [
        AdminReportItem.model_validate(
            {
                "id": r.id,
                "reporter_id": r.reporter_id,
                "reporter_email": reporter_email,
                "reported_user_id": r.reported_user_id,
                "reported_email": reported_email,
                "room_id": r.room_id,
                "reason": r.reason,
                "description": r.description,
                "status": r.status,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
        )
        for r, reporter_email, reported_email in rows
    ]


async def list_queue(
    db: AsyncSession,
    *,
    include_assigned: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminQueueItem]:
    """Rooms ready for planner assignment.

    Default: only VIABLE + unassigned (the actual queue).
    With include_assigned=True: also include ASSIGNED rooms (newly handed off,
    not yet planner-confirmed).
    """
    statuses = [RoomStatus.VIABLE.value]
    if include_assigned:
        statuses.append(RoomStatus.ASSIGNED.value)

    host_u = User.__table__.alias("host_u")
    host_p = Profile.__table__.alias("host_p")
    q = (
        select(Room, host_u.c.email, host_p.c.display_name, Planner.name)
        .join(host_u, host_u.c.id == Room.host_user_id)
        .outerjoin(host_p, host_p.c.user_id == Room.host_user_id)
        .outerjoin(Planner, Planner.id == Room.planner_id)
        .where(Room.status.in_(statuses))
        .order_by(Room.viable_at.asc().nullslast(), Room.starts_at.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(q)).all()

    out: list[AdminQueueItem] = []
    for r, host_email, host_name, planner_name in rows:
        summary = await host_service.get_capacity_summary(db, r.id, r)
        out.append(
            AdminQueueItem.model_validate(
                {
                    "id": r.id,
                    "title": r.title,
                    "region": r.region,
                    "starts_at": r.starts_at,
                    "male_capacity": r.male_capacity,
                    "female_capacity": r.female_capacity,
                    "male_confirmed": summary.male_confirmed,
                    "female_confirmed": summary.female_confirmed,
                    "viable_at": r.viable_at,
                    "host_user_id": r.host_user_id,
                    "host_email": host_email,
                    "host_display_name": host_name,
                    "planner_id": r.planner_id,
                    "planner_name": planner_name,
                    "status": r.status,
                }
            )
        )
    return out


async def assign_planner_to_room(
    db: AsyncSession,
    actor: User,
    room_id: UUID,
    planner_id: UUID,
    ip: str | None,
    ua: str | None,
) -> Room:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.status not in (RoomStatus.VIABLE.value, RoomStatus.ASSIGNED.value):
        raise InvalidStateTransition(
            f"Only VIABLE or ASSIGNED rooms can be (re)assigned (was '{room.status}')."
        )
    planner = await db.scalar(select(Planner).where(Planner.id == planner_id))
    if planner is None:
        raise NotFound("PLANNER_NOT_FOUND", "Planner not found.")
    if planner.status != PlannerStatus.APPROVED.value:
        raise APIError(
            "PLANNER_NOT_APPROVED",
            f"Planner is {planner.status}.",
            status_code=409,
        )

    before = {
        "planner_id": str(room.planner_id) if room.planner_id else None,
        "status": room.status,
    }
    room.planner_id = planner.id
    room.status = RoomStatus.ASSIGNED.value
    await db.flush()
    await audit_service.log_action(
        db,
        actor=actor,
        action="room.assigned",
        entity_type="room",
        entity_id=room.id,
        before=before,
        after={"planner_id": str(planner.id), "status": room.status},
        ip_address=ip,
        user_agent=ua,
    )
    return room


async def set_report_status(
    db: AsyncSession,
    actor: User,
    report_id: UUID,
    new_status: ReportStatus,
    ip: str | None,
    ua: str | None,
    note: str | None = None,
) -> Report:
    report = await db.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise NotFound("REPORT_NOT_FOUND", "Report not found.")
    if report.status not in (ReportStatus.OPEN.value, ReportStatus.INVESTIGATING.value):
        raise InvalidStateTransition(
            f"Cannot change report from '{report.status}'."
        )
    before = {"status": report.status, "description": report.description}
    report.status = new_status.value
    if note is not None:
        # Append the note to description for context.
        report.description = (report.description or "") + f"\n[admin] {note}"
    await db.flush()
    await audit_service.log_action(
        db,
        actor=actor,
        action=f"report.{new_status.value}",
        entity_type="report",
        entity_id=report.id,
        before=before,
        after={"status": report.status, "description": report.description},
        ip_address=ip,
        user_agent=ua,
    )
    return report
