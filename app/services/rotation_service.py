from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import APIError, Forbidden, InvalidStateTransition, NotFound
from app.models import (
    CheckIn,
    Planner,
    Profile,
    Room,
    RotationRound,
    RotationSession,
    SeatAssignment,
    User,
)
from app.models._enums import (
    CheckInStatus,
    Gender,
    RoomStatus,
    RotationRoundStatus,
    RotationSessionStatus,
)
from app.schemas.rotation import (
    MyCurrentRoundView,
    OpponentBrief,
    RoundView,
    RotationSessionView,
    SeatPair,
)


async def _get_owned_room(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> Room:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.planner_id != planner.id:
        raise Forbidden("You do not own this room.")
    return room


def _round_robin_pairs(
    males: list[UUID], females: list[UUID]
) -> list[list[tuple[int, UUID, UUID]]]:
    """For balanced N:N, generate N rounds where every male meets every female once.

    Returns rounds; each round is a list of (table_number, male_id, female_id).
    """
    n = len(males)
    rounds: list[list[tuple[int, UUID, UUID]]] = []
    for r in range(n):
        seats: list[tuple[int, UUID, UUID]] = []
        for i in range(n):
            seats.append((i + 1, males[i], females[(i + r) % n]))
        rounds.append(seats)
    return rounds


async def start_session(
    db: AsyncSession,
    planner: Planner,
    room_id: UUID,
    round_duration_minutes: int = 12,
) -> RotationSession:
    room = await _get_owned_room(db, planner, room_id)
    if room.status != RoomStatus.CONFIRMED.value:
        raise InvalidStateTransition(
            f"Rotation can only start on CONFIRMED rooms (was '{room.status}')."
        )

    existing = await db.scalar(
        select(RotationSession).where(RotationSession.room_id == room_id)
    )
    if existing is not None:
        raise APIError(
            "ROTATION_ALREADY_STARTED",
            "Rotation has already been started for this room.",
            status_code=409,
        )

    # Gather CHECKED_IN participants and split by gender via Profile.
    rows = (
        await db.execute(
            select(CheckIn.user_id, Profile.gender)
            .join(Profile, Profile.user_id == CheckIn.user_id)
            .where(
                CheckIn.room_id == room_id,
                CheckIn.status == CheckInStatus.CHECKED_IN.value,
            )
        )
    ).all()
    males = sorted([uid for uid, g in rows if g == Gender.MALE.value])
    females = sorted([uid for uid, g in rows if g == Gender.FEMALE.value])
    if not males or not females:
        raise APIError(
            "NO_CHECKED_IN_PARTICIPANTS",
            "Both genders need at least one checked-in participant.",
            status_code=409,
        )
    if len(males) != len(females):
        raise APIError(
            "ROTATION_GENDER_IMBALANCE",
            f"Male/female checked-in counts must match (M={len(males)}, F={len(females)}).",
            status_code=409,
        )

    n = len(males)
    pairs_by_round = _round_robin_pairs(males, females)

    started_at = datetime.now(timezone.utc)
    session = RotationSession(
        room_id=room_id,
        status=RotationSessionStatus.RUNNING.value,
        current_round=1,
        round_duration_minutes=round_duration_minutes,
        started_at=started_at,
    )
    db.add(session)
    await db.flush()

    duration = timedelta(minutes=round_duration_minutes)
    for r_idx, seats in enumerate(pairs_by_round):
        rnd = RotationRound(
            session_id=session.id,
            room_id=room_id,
            round_number=r_idx + 1,
            status=(
                RotationRoundStatus.ACTIVE.value
                if r_idx == 0
                else RotationRoundStatus.PENDING.value
            ),
            starts_at=started_at + duration * r_idx,
            ends_at=started_at + duration * (r_idx + 1),
        )
        db.add(rnd)
        await db.flush()
        for tbl, male_id, female_id in seats:
            db.add(
                SeatAssignment(
                    room_id=room_id,
                    session_id=session.id,
                    round_id=rnd.id,
                    participant_a_id=male_id,
                    participant_b_id=female_id,
                    table_number=tbl,
                )
            )

    room.status = RoomStatus.IN_PROGRESS.value
    await db.flush()
    return session


async def next_round(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> RotationSession:
    await _get_owned_room(db, planner, room_id)
    session = await db.scalar(
        select(RotationSession).where(RotationSession.room_id == room_id)
    )
    if session is None:
        raise NotFound("ROTATION_NOT_STARTED", "Rotation has not started.")
    if session.status != RotationSessionStatus.RUNNING.value:
        raise InvalidStateTransition(
            f"Cannot advance from session state '{session.status}'."
        )

    rounds = list(
        (
            await db.scalars(
                select(RotationRound)
                .where(RotationRound.session_id == session.id)
                .order_by(RotationRound.round_number.asc())
            )
        ).all()
    )
    total = len(rounds)
    if session.current_round >= total:
        raise APIError(
            "ALREADY_LAST_ROUND",
            "This is the last round; end the session instead.",
            status_code=409,
        )

    current = next((r for r in rounds if r.round_number == session.current_round), None)
    if current is not None:
        current.status = RotationRoundStatus.COMPLETED.value
        current.ends_at = datetime.now(timezone.utc)
    next_r = next(
        (r for r in rounds if r.round_number == session.current_round + 1), None
    )
    if next_r is not None:
        next_r.status = RotationRoundStatus.ACTIVE.value
        next_r.starts_at = datetime.now(timezone.utc)
        next_r.ends_at = next_r.starts_at + timedelta(
            minutes=session.round_duration_minutes
        )

    session.current_round += 1
    await db.flush()
    return session


async def end_session(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> RotationSession:
    room = await _get_owned_room(db, planner, room_id)
    session = await db.scalar(
        select(RotationSession).where(RotationSession.room_id == room_id)
    )
    if session is None:
        raise NotFound("ROTATION_NOT_STARTED", "Rotation has not started.")
    if session.status == RotationSessionStatus.COMPLETED.value:
        raise InvalidStateTransition("Session is already completed.")

    rounds = list(
        (
            await db.scalars(
                select(RotationRound).where(RotationRound.session_id == session.id)
            )
        ).all()
    )
    now = datetime.now(timezone.utc)
    for r in rounds:
        if r.status != RotationRoundStatus.COMPLETED.value:
            r.status = RotationRoundStatus.COMPLETED.value
            r.ends_at = r.ends_at or now
    session.status = RotationSessionStatus.COMPLETED.value
    session.ended_at = now
    room.status = RoomStatus.COMPLETED.value
    await db.flush()
    return session


async def get_session_view(
    db: AsyncSession, planner: Planner, room_id: UUID
) -> RotationSessionView:
    await _get_owned_room(db, planner, room_id)
    session = await db.scalar(
        select(RotationSession)
        .options(selectinload(RotationSession.rounds))
        .where(RotationSession.room_id == room_id)
    )
    if session is None:
        raise NotFound("ROTATION_NOT_STARTED", "Rotation has not started.")

    seats = (
        await db.scalars(
            select(SeatAssignment).where(SeatAssignment.session_id == session.id)
        )
    ).all()
    seats_by_round: dict[UUID, list[SeatAssignment]] = {}
    for s in seats:
        seats_by_round.setdefault(s.round_id, []).append(s)

    user_ids = {s.participant_a_id for s in seats} | {
        s.participant_b_id for s in seats
    }
    profiles = (
        await db.scalars(select(Profile).where(Profile.user_id.in_(user_ids)))
    ).all()
    name_by_user = {p.user_id: p.display_name for p in profiles}

    rounds_view: list[RoundView] = []
    for rnd in sorted(session.rounds, key=lambda r: r.round_number):
        rseats = sorted(
            seats_by_round.get(rnd.id, []), key=lambda s: s.table_number
        )
        rounds_view.append(
            RoundView(
                id=rnd.id,
                round_number=rnd.round_number,
                status=rnd.status,
                starts_at=rnd.starts_at,
                ends_at=rnd.ends_at,
                seats=[
                    SeatPair(
                        table_number=s.table_number,
                        participant_a_id=s.participant_a_id,
                        participant_b_id=s.participant_b_id,
                        participant_a_name=name_by_user.get(s.participant_a_id),
                        participant_b_name=name_by_user.get(s.participant_b_id),
                    )
                    for s in rseats
                ],
            )
        )
    return RotationSessionView(
        id=session.id,
        room_id=session.room_id,
        status=session.status,
        current_round=session.current_round,
        round_duration_minutes=session.round_duration_minutes,
        started_at=session.started_at,
        ended_at=session.ended_at,
        rounds=rounds_view,
    )


async def get_my_current_round(
    db: AsyncSession, user: User, room_id: UUID
) -> MyCurrentRoundView:
    session = await db.scalar(
        select(RotationSession).where(RotationSession.room_id == room_id)
    )
    if session is None:
        raise NotFound("ROTATION_NOT_STARTED", "Rotation has not started.")

    rounds = list(
        (
            await db.scalars(
                select(RotationRound)
                .where(RotationRound.session_id == session.id)
                .order_by(RotationRound.round_number.asc())
            )
        ).all()
    )
    total_rounds = len(rounds)
    current_round_number = session.current_round
    current_round = next(
        (r for r in rounds if r.round_number == current_round_number), None
    )
    if current_round is None:
        return MyCurrentRoundView(
            session_status=session.status,
            current_round=current_round_number,
            total_rounds=total_rounds,
            round_duration_minutes=session.round_duration_minutes,
        )

    seat = await db.scalar(
        select(SeatAssignment).where(
            SeatAssignment.round_id == current_round.id,
            (
                (SeatAssignment.participant_a_id == user.id)
                | (SeatAssignment.participant_b_id == user.id)
            ),
        )
    )

    opponent: OpponentBrief | None = None
    table_number: int | None = None
    if seat is not None:
        table_number = seat.table_number
        opp_id = (
            seat.participant_b_id
            if seat.participant_a_id == user.id
            else seat.participant_a_id
        )
        opp_profile = await db.scalar(select(Profile).where(Profile.user_id == opp_id))
        if opp_profile is not None:
            opponent = OpponentBrief(
                user_id=opp_profile.user_id,
                display_name=opp_profile.display_name,
                gender=opp_profile.gender,
                birth_year=opp_profile.birth_year,
                region=opp_profile.region,
                job_title=opp_profile.job_title,
                intro=opp_profile.intro,
            )

    return MyCurrentRoundView(
        session_status=session.status,
        current_round=current_round_number,
        total_rounds=total_rounds,
        round_duration_minutes=session.round_duration_minutes,
        table_number=table_number,
        opponent=opponent,
        round_status=current_round.status,
    )
