"""Seed initial users, planner, and a sample room.

Run inside the API container:
    poetry run python -m app.scripts.seed

Idempotent: skips records that already exist (matched by email/title).
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models import Planner, Profile, Room, User
from app.models._enums import (
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


async def _ensure_user(session, spec: dict) -> User:
    user = await session.scalar(select(User).where(User.email == spec["email"]))
    if user is not None:
        return user
    user = User(
        email=spec["email"],
        password_hash=hash_password(spec["password"]),
        role=spec["role"].value,
        status=UserStatus.ACTIVE.value,
    )
    session.add(user)
    await session.flush()
    print(f"  + user {user.email} ({user.role})")
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


async def _ensure_seed_room(session, planner: Planner) -> None:
    title = "강남 직장인 3:3 롤링"
    existing = await session.scalar(select(Room).where(Room.title == title))
    if existing is not None:
        return
    starts_at = datetime.now(timezone.utc) + timedelta(days=7)
    ends_at = starts_at + timedelta(hours=3)
    room = Room(
        planner_id=planner.id,
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
    )
    session.add(room)
    print(f"    + seed room '{title}'")


async def run() -> None:
    async with AsyncSessionLocal() as session:
        print("Seeding users…")
        planner_obj: Planner | None = None
        for spec in SEED_USERS:
            user = await _ensure_user(session, spec)
            await _ensure_profile(session, user, spec.get("profile"))
            if spec["role"] == UserRole.PLANNER:
                planner_obj = await _ensure_planner(session, user, spec.get("planner"))

        if planner_obj is not None:
            print("Seeding sample room…")
            await _ensure_seed_room(session, planner_obj)

        await session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(run())
