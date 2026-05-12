from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import APIResponse
from app.schemas.profile import ProfileResponse, ProfileUpsert
from app.services import profile_service

router = APIRouter()


@router.get("/me", response_model=APIResponse[ProfileResponse])
async def get_me(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ProfileResponse]:
    profile = await profile_service.get_my_profile(db, user)
    return APIResponse(data=ProfileResponse.model_validate(profile))


@router.put("/me", response_model=APIResponse[ProfileResponse])
async def upsert_me(
    body: ProfileUpsert,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ProfileResponse]:
    profile = await profile_service.upsert_my_profile(db, user, body)
    await db.commit()
    await db.refresh(profile)
    return APIResponse(data=ProfileResponse.model_validate(profile))
