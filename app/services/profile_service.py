from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models import Profile, User
from app.schemas.profile import ProfileUpsert


async def get_my_profile(db: AsyncSession, user: User) -> Profile:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        raise NotFound("PROFILE_NOT_FOUND", "Profile has not been created yet.")
    return profile


async def upsert_my_profile(
    db: AsyncSession, user: User, body: ProfileUpsert
) -> Profile:
    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    payload = body.model_dump()
    payload["gender"] = body.gender.value

    if profile is None:
        profile = Profile(user_id=user.id, **payload)
        db.add(profile)
    else:
        for key, value in payload.items():
            setattr(profile, key, value)
    await db.flush()
    return profile


def is_profile_complete(profile: Profile | None) -> bool:
    if profile is None:
        return False
    return all(
        [
            profile.display_name,
            profile.gender,
            profile.birth_year,
            profile.region,
        ]
    )
