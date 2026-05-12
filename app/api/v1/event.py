from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.checkin import MyCheckInView
from app.schemas.common import APIResponse
from app.schemas.rotation import MyCurrentRoundView
from app.services import checkin_service, rotation_service

router = APIRouter()


@router.get("/{room_id}/checkin", response_model=APIResponse[MyCheckInView])
async def my_checkin(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[MyCheckInView]:
    ck = await checkin_service.get_my_checkin(db, user, room_id)
    return APIResponse(data=MyCheckInView.model_validate(ck))


@router.get(
    "/{room_id}/rotation/current",
    response_model=APIResponse[MyCurrentRoundView],
)
async def my_current_round(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[MyCurrentRoundView]:
    view = await rotation_service.get_my_current_round(db, user, room_id)
    return APIResponse(data=view)
