from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models._enums import RoomType
from app.schemas.application import ApplicationCreate, ApplicationResponse
from app.schemas.common import APIResponse
from app.schemas.room import RoomDetail, RoomListResponse
from app.services import application_service, room_service

router = APIRouter()


@router.get("", response_model=APIResponse[RoomListResponse])
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    region: str | None = Query(default=None),
    room_type: RoomType | None = Query(default=None),
    starts_after: datetime | None = Query(default=None),
    starts_before: datetime | None = Query(default=None),
    min_age: int | None = Query(default=None, ge=18, le=99),
    max_age: int | None = Query(default=None, ge=18, le=99),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[RoomListResponse]:
    rooms, total = await room_service.list_public_rooms(
        db,
        region=region,
        room_type=room_type,
        starts_after=starts_after,
        starts_before=starts_before,
        min_age=min_age,
        max_age=max_age,
        limit=limit,
        offset=offset,
    )
    items = [room_service.to_list_item(r) for r in rooms]
    return APIResponse(
        data=RoomListResponse(items=items, total=total, limit=limit, offset=offset)
    )


@router.get("/{room_id}", response_model=APIResponse[RoomDetail])
async def get_room(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[RoomDetail]:
    room = await room_service.get_public_room(db, room_id)
    capacity = await room_service.get_capacity_summary(db, room_id, room)
    return APIResponse(data=room_service.to_detail(room, capacity))


@router.post(
    "/{room_id}/apply",
    response_model=APIResponse[ApplicationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def apply_room(
    room_id: UUID,
    body: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ApplicationResponse]:
    app = await application_service.apply_to_room(db, user, room_id, body.applicant_message)
    await db.commit()
    await db.refresh(app)
    return APIResponse(data=ApplicationResponse.model_validate(app))
