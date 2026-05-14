"""Seed initial users, planner, and sample rooms.

Run inside the API container:
    poetry run python -m app.scripts.seed

Idempotent: skips records that already exist (matched by email/title).
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import Credit, Planner, Profile, Room, User
from app.models._enums import (
    CreditKind,
    CreditSource,
    CreditStatus,
    Gender,
    PlannerStatus,
    RoomStatus,
    RoomType,
    RoomVisibility,
    UserRole,
    UserStatus,
)


SEED_USERS = [
    {
        "email": "admin@example.com",
        "password": "admin1234",
        "role": UserRole.ADMIN,
        "profile": None,
    },
    {
        "email": "planner@example.com",
        "password": "planner1234",
        "role": UserRole.PLANNER,
        "profile": {
            "display_name": "강남 플래너",
            "gender": Gender.MALE,
            "birth_year": 1990,
            "region": "서울 강남",
        },
        "planner": {
            "name": "강남 롤링 운영팀",
            "bio": "서울 강남 직장인 대상 롤링방을 운영합니다.",
            "region": "서울 강남",
            "status": PlannerStatus.APPROVED,
        },
    },
    {
        "email": "alice@example.com",
        "password": "alice1234",
        "role": UserRole.PARTICIPANT,
        "profile": {
            "display_name": "앨리스",
            "gender": Gender.FEMALE,
            "birth_year": 1995,
            "region": "서울 강남",
            "job_title": "디자이너",
            "intro": "안녕하세요! 새로운 만남이 즐거운 디자이너예요.",
        },
        "welcome_credit": True,  # demo: show how welcome credit looks
    },
    {
        "email": "participant1@example.com",
        "password": "participant1234",
        "role": UserRole.PARTICIPANT,
        "profile": {
            "display_name": "지원자1",
            "gender": Gender.MALE,
            "birth_year": 1992,
            "region": "서울 송파",
        },
    },
    {
        "email": "participant2@example.com",
        "password": "participant1234",
        "role": UserRole.PARTICIPANT,
        "profile": {
            "display_name": "지원자2",
            "gender": Gender.FEMALE,
            "birth_year": 1994,
            "region": "서울 마포",
        },
    },
]


def _stable_referral_code(email: str) -> str:
    """Deterministic 6-char referral code for seed users."""
    return hashlib.md5(email.encode()).hexdigest()[:6].upper()


async def _ensure_user(session, spec: dict) -> User:
    user = await session.scalar(select(User).where(User.email == spec["email"]))
    if user is not None:
        # Backfill referral_code if somehow missing.
        if not user.referral_code:
            user.referral_code = _stable_referral_code(spec["email"])
            await session.flush()
        return user
    user = User(
        email=spec["email"],
        password_hash=hash_password(spec["password"]),
        role=spec["role"].value,
        status=UserStatus.ACTIVE.value,
        referral_code=_stable_referral_code(spec["email"]),
    )
    session.add(user)
    await session.flush()
    print(f"  + user {user.email} ({user.role}) — ref {user.referral_code}")
    return user


async def _ensure_profile(session, user: User, spec: dict | None) -> None:
    if spec is None:
        return
    existing = await session.scalar(select(Profile).where(Profile.user_id == user.id))
    if existing is not None:
        return
    profile = Profile(
        user_id=user.id,
        display_name=spec["display_name"],
        gender=spec["gender"].value,
        birth_year=spec["birth_year"],
        region=spec.get("region"),
        job_title=spec.get("job_title"),
        intro=spec.get("intro"),
    )
    session.add(profile)
    print(f"    + profile for {user.email}")


async def _ensure_planner(session, user: User, spec: dict | None) -> Planner | None:
    if spec is None:
        return None
    existing = await session.scalar(select(Planner).where(Planner.user_id == user.id))
    if existing is not None:
        return existing
    planner = Planner(
        user_id=user.id,
        name=spec["name"],
        bio=spec.get("bio"),
        region=spec.get("region"),
        status=spec["status"].value,
    )
    session.add(planner)
    await session.flush()
    print(f"    + planner profile for {user.email}")
    return planner


async def _ensure_welcome_credit(session, user: User) -> None:
    """Demo: a 3,000원 manual_grant so new beta testers see how credits look."""
    existing = await session.scalar(
        select(Credit).where(
            Credit.user_id == user.id,
            Credit.source == CreditSource.MANUAL_GRANT.value,
        )
    )
    if existing is not None:
        return
    credit = Credit(
        user_id=user.id,
        kind=CreditKind.FIXED_AMOUNT.value,
        amount_krw=3_000,
        status=CreditStatus.ACTIVE.value,
        source=CreditSource.MANUAL_GRANT.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=90),
        description="베타 환영 — 첫 방 3,000원 할인",
    )
    session.add(credit)
    print(f"    + welcome credit for {user.email}")


async def _ensure_planner_seed_room(session, planner_host_user_id, planner_id: object) -> None:
    title = "강남 직장인 3:3 롤링"
    existing = await session.scalar(select(Room).where(Room.title == title))
    if existing is not None:
        return
    starts_at = datetime.now(timezone.utc) + timedelta(days=7)
    ends_at = starts_at + timedelta(hours=3)
    room = Room(
        host_user_id=planner_host_user_id,
        planner_id=planner_id,
        title=title,
        subtitle="토요일 저녁, 부담 없이 한 바퀴",
        description="강남 직장인 대상 3:3 로테이션 소개팅 모임입니다.",
        room_type=RoomType.THREE_BY_THREE.value,
        status=RoomStatus.PUBLISHED.value,
        region="서울 강남",
        venue_name="강남 모처",
        venue_address="서울특별시 강남구 (당일 안내)",
        starts_at=starts_at,
        ends_at=ends_at,
        min_age=27,
        max_age=35,
        male_capacity=3,
        female_capacity=3,
        price_amount=15000,
        deposit_amount=10000,
        currency="KRW",
        application_deadline=starts_at - timedelta(days=2),
        visibility=RoomVisibility.PUBLIC.value,
        payment_instructions=(
            "💳 결제 안내\n"
            "카카오뱅크 3333-12-345678 (강남 롤링 운영팀)\n"
            "참가비 15,000원 + 보증금 10,000원 = 총 25,000원\n\n"
            "승인 후 24시간 내 입금 부탁드려요. 보증금은 정상 참석 시 환급됩니다."
        ),
    )
    session.add(room)
    print(f"    + seed room '{title}' (host=planner)")


async def _ensure_user_hosted_room(session, host_user: User) -> None:
    """Demonstrates 'anyone can host': a participant-as-host room in DRAFT."""
    title = "성수 4:4 토요일 저녁"
    existing = await session.scalar(select(Room).where(Room.title == title))
    if existing is not None:
        return
    starts_at = datetime.now(timezone.utc) + timedelta(days=10)
    ends_at = starts_at + timedelta(hours=3)
    room = Room(
        host_user_id=host_user.id,
        planner_id=None,
        title=title,
        subtitle="성수동 직장인 4:4, 가볍게 한 잔",
        description=(
            "성수동에서 일하는 또래들 (28-34세) 대상으로 한 4:4 모임이에요.\n"
            "친구들끼리 와도 좋고, 혼자 와도 좋아요. 부담 없이 시작해봐요!"
        ),
        room_type=RoomType.FOUR_BY_FOUR.value,
        status=RoomStatus.DRAFT.value,
        region="서울 성수",
        starts_at=starts_at,
        ends_at=ends_at,
        min_age=28,
        max_age=34,
        male_capacity=4,
        female_capacity=4,
        price_amount=18000,
        deposit_amount=12000,
        currency="KRW",
        application_deadline=starts_at - timedelta(days=2),
        visibility=RoomVisibility.PUBLIC.value,
        payment_instructions=(
            "💳 결제 안내 (베타)\n"
            "토스뱅크 1000-1234-5678 앨리스\n"
            "참가비 18,000원 + 보증금 12,000원 = 총 30,000원\n\n"
            "송금 메모에 본인 이름 기재 부탁드려요!"
        ),
    )
    session.add(room)
    print(f"    + seed room '{title}' (host={host_user.email})")


async def run() -> None:
    async with AsyncSessionLocal() as session:
        print("Seeding users…")
        planner_obj: Planner | None = None
        planner_user: User | None = None
        alice_user: User | None = None
        for spec in SEED_USERS:
            user = await _ensure_user(session, spec)
            await _ensure_profile(session, user, spec.get("profile"))
            if spec["role"] == UserRole.PLANNER:
                planner_obj = await _ensure_planner(session, user, spec.get("planner"))
                planner_user = user
            if spec.get("welcome_credit"):
                await _ensure_welcome_credit(session, user)
            if spec["email"] == "alice@example.com":
                alice_user = user

        if planner_obj is not None and planner_user is not None:
            print("Seeding planner-as-host sample room…")
            await _ensure_planner_seed_room(
                session,
                planner_host_user_id=planner_user.id,
                planner_id=planner_obj.id,
            )

        if alice_user is not None:
            print("Seeding participant-as-host sample room (DRAFT)…")
            await _ensure_user_hosted_room(session, alice_user)

        await session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(run())
