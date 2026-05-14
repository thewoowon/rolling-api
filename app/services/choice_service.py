from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    APIError,
    Conflict,
    Forbidden,
    InvalidStateTransition,
    NotFound,
)
from app.models import (
    AfterDateProposal,
    CheckIn,
    MatchResult,
    ParticipantChoice,
    Profile,
    Room,
    User,
)
from app.models._enums import (
    AfterDateProposalStatus,
    CheckInStatus,
    ChoiceType,
    MatchStatus,
    RoomStatus,
)
from app.schemas.choice import (
    AfterDateProposalCreate,
    AfterDateProposalResponse,
    ChoiceItem,
    ChoiceTarget,
    MatchSummary,
)


CHOICE_OPEN_STATUSES = (
    RoomStatus.IN_PROGRESS.value,
    RoomStatus.COMPLETED.value,
)


def _canonical_pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    return (a, b) if str(a) < str(b) else (b, a)


async def _ensure_attended(
    db: AsyncSession, user: User, room: Room
) -> CheckIn:
    ck = await db.scalar(
        select(CheckIn).where(
            CheckIn.room_id == room.id,
            CheckIn.user_id == user.id,
            CheckIn.status == CheckInStatus.CHECKED_IN.value,
        )
    )
    if ck is None:
        raise Forbidden("Only checked-in attendees can do this.")
    return ck


async def list_choice_targets(
    db: AsyncSession, user: User, room_id: UUID
) -> list[ChoiceTarget]:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.status not in CHOICE_OPEN_STATUSES:
        raise InvalidStateTransition(
            "Choices are not yet available for this room."
        )

    me_profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if me_profile is None:
        raise Forbidden("Profile is required.")
    await _ensure_attended(db, user, room)

    rows = (
        await db.execute(
            select(Profile, CheckIn)
            .join(CheckIn, CheckIn.user_id == Profile.user_id)
            .where(
                CheckIn.room_id == room_id,
                CheckIn.status == CheckInStatus.CHECKED_IN.value,
                Profile.user_id != user.id,
                Profile.gender != me_profile.gender,
            )
            .order_by(Profile.display_name.asc())
        )
    ).all()

    my_choices_rows = (
        await db.scalars(
            select(ParticipantChoice).where(
                ParticipantChoice.room_id == room_id,
                ParticipantChoice.chooser_id == user.id,
            )
        )
    ).all()
    my_choice_by_chosen = {c.chosen_id: c.choice_type for c in my_choices_rows}

    return [
        ChoiceTarget(
            user_id=p.user_id,
            display_name=p.display_name,
            gender=p.gender,
            birth_year=p.birth_year,
            region=p.region,
            job_title=p.job_title,
            intro=p.intro,
            my_choice=my_choice_by_chosen.get(p.user_id),
        )
        for p, _ in rows
    ]


async def submit_choices(
    db: AsyncSession, user: User, room_id: UUID, choices: list[ChoiceItem]
) -> tuple[int, int]:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    if room.status not in CHOICE_OPEN_STATUSES:
        raise InvalidStateTransition(
            "Choices are not yet available for this room."
        )
    me_profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if me_profile is None:
        raise Forbidden("Profile is required.")
    await _ensure_attended(db, user, room)

    # Map valid targets in this room (opposite gender, checked-in).
    target_rows = (
        await db.execute(
            select(Profile.user_id)
            .join(CheckIn, CheckIn.user_id == Profile.user_id)
            .where(
                CheckIn.room_id == room_id,
                CheckIn.status == CheckInStatus.CHECKED_IN.value,
                Profile.gender != me_profile.gender,
                Profile.user_id != user.id,
            )
        )
    ).all()
    valid_targets = {row[0] for row in target_rows}

    accepted = 0
    new_mutual = 0
    now = datetime.now(timezone.utc)

    for item in choices:
        if item.chosen_id not in valid_targets:
            raise APIError(
                "INVALID_CHOICE_TARGET",
                f"User {item.chosen_id} is not a valid choice target.",
                status_code=409,
            )
        existing = await db.scalar(
            select(ParticipantChoice).where(
                ParticipantChoice.room_id == room_id,
                ParticipantChoice.chooser_id == user.id,
                ParticipantChoice.chosen_id == item.chosen_id,
            )
        )
        prev_type = existing.choice_type if existing else None
        if existing is None:
            existing = ParticipantChoice(
                room_id=room_id,
                chooser_id=user.id,
                chosen_id=item.chosen_id,
                choice_type=item.choice_type.value,
                note=item.note,
            )
            db.add(existing)
        else:
            existing.choice_type = item.choice_type.value
            existing.note = item.note
        accepted += 1

        # If interested, check the reverse and (de)materialize MatchResult.
        if item.choice_type == ChoiceType.INTERESTED:
            reverse = await db.scalar(
                select(ParticipantChoice).where(
                    ParticipantChoice.room_id == room_id,
                    ParticipantChoice.chooser_id == item.chosen_id,
                    ParticipantChoice.chosen_id == user.id,
                    ParticipantChoice.choice_type == ChoiceType.INTERESTED.value,
                )
            )
            if reverse is not None:
                ua, ub = _canonical_pair(user.id, item.chosen_id)
                match = await db.scalar(
                    select(MatchResult).where(
                        MatchResult.room_id == room_id,
                        MatchResult.user_a_id == ua,
                        MatchResult.user_b_id == ub,
                    )
                )
                if match is None:
                    # Host of this room sees the match immediately; other
                    # participants see it 24h after creation. This gives the
                    # host a first-mover window to propose an after-date.
                    visible_at = datetime.now(timezone.utc) + timedelta(hours=24)
                    db.add(
                        MatchResult(
                            room_id=room_id,
                            user_a_id=ua,
                            user_b_id=ub,
                            status=MatchStatus.MUTUAL.value,
                            visible_at=visible_at,
                        )
                    )
                    new_mutual += 1
                elif match.status == MatchStatus.NONE.value:
                    match.status = MatchStatus.MUTUAL.value
                    if match.visible_at is None:
                        match.visible_at = datetime.now(timezone.utc) + timedelta(hours=24)
                    new_mutual += 1
        else:
            # If user changed away from interested, downgrade existing match (if any).
            if prev_type == ChoiceType.INTERESTED.value:
                ua, ub = _canonical_pair(user.id, item.chosen_id)
                match = await db.scalar(
                    select(MatchResult).where(
                        MatchResult.room_id == room_id,
                        MatchResult.user_a_id == ua,
                        MatchResult.user_b_id == ub,
                    )
                )
                if match is not None and match.status in (
                    MatchStatus.MUTUAL.value,
                    MatchStatus.AFTER_PROPOSED.value,
                ):
                    match.status = MatchStatus.NONE.value

    await db.flush()
    _ = now  # reserved for potential timestamping
    return accepted, new_mutual


async def list_my_matches(
    db: AsyncSession, user: User, room_id: UUID
) -> list[MatchSummary]:
    room = await db.scalar(select(Room).where(Room.id == room_id))
    if room is None:
        raise NotFound("ROOM_NOT_FOUND", "Room not found.")
    await _ensure_attended(db, user, room)

    # Host of the room sees all matches immediately; non-host participants
    # see only those whose `visible_at` is in the past (24h embargo).
    is_host = room.host_user_id == user.id
    now = datetime.now(timezone.utc)
    base_q = select(MatchResult).where(
        MatchResult.room_id == room_id,
        or_(
            MatchResult.user_a_id == user.id,
            MatchResult.user_b_id == user.id,
        ),
        MatchResult.status.in_(
            (
                MatchStatus.MUTUAL.value,
                MatchStatus.AFTER_PROPOSED.value,
                MatchStatus.AFTER_CONFIRMED.value,
            )
        ),
    )
    if not is_host:
        base_q = base_q.where(
            or_(MatchResult.visible_at.is_(None), MatchResult.visible_at <= now)
        )
    matches = list((await db.scalars(base_q)).all())
    if not matches:
        return []

    counterpart_ids = {
        m.user_b_id if m.user_a_id == user.id else m.user_a_id for m in matches
    }
    profiles = (
        await db.scalars(
            select(Profile).where(Profile.user_id.in_(counterpart_ids))
        )
    ).all()
    by_uid = {p.user_id: p for p in profiles}

    proposals = (
        await db.scalars(
            select(AfterDateProposal).where(
                AfterDateProposal.match_result_id.in_([m.id for m in matches])
            )
        )
    ).all()
    proposed_match_ids = {p.match_result_id for p in proposals}

    out: list[MatchSummary] = []
    for m in matches:
        cid = m.user_b_id if m.user_a_id == user.id else m.user_a_id
        p = by_uid.get(cid)
        out.append(
            MatchSummary(
                id=m.id,
                room_id=m.room_id,
                status=m.status,
                counterpart_user_id=cid,
                counterpart_name=p.display_name if p else None,
                counterpart_gender=p.gender if p else None,
                counterpart_birth_year=p.birth_year if p else None,
                counterpart_region=p.region if p else None,
                counterpart_job_title=p.job_title if p else None,
                counterpart_intro=p.intro if p else None,
                after_proposed=m.id in proposed_match_ids,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
        )
    return out


async def propose_after_date(
    db: AsyncSession,
    user: User,
    match_id: UUID,
    body: AfterDateProposalCreate,
) -> AfterDateProposalResponse:
    match = await db.scalar(select(MatchResult).where(MatchResult.id == match_id))
    if match is None:
        raise NotFound("MATCH_NOT_FOUND", "Match not found.")
    if user.id not in (match.user_a_id, match.user_b_id):
        raise Forbidden("You are not part of this match.")
    if match.status not in (
        MatchStatus.MUTUAL.value,
        MatchStatus.AFTER_PROPOSED.value,
    ):
        raise InvalidStateTransition(
            f"Cannot propose from match state '{match.status}'."
        )

    proposal = AfterDateProposal(
        match_result_id=match.id,
        proposer_id=user.id,
        proposed_date=body.proposed_date,
        proposed_place=body.proposed_place,
        status=AfterDateProposalStatus.PROPOSED.value,
    )
    db.add(proposal)
    if match.status == MatchStatus.MUTUAL.value:
        match.status = MatchStatus.AFTER_PROPOSED.value
    await db.flush()
    return AfterDateProposalResponse.model_validate(proposal)
