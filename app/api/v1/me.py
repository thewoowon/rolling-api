from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.application import (
    ApplicationResponse,
    MyApplicationItem,
    RoomBriefForApplication,
)
from app.schemas.common import APIResponse
from app.schemas.credit import CreditItem, CreditWallet
from app.schemas.room import RoomListItem
from app.services import application_service, credit_service
from app.models._enums import CreditKind, CreditStatus

router = APIRouter()


@router.get("/applications", response_model=APIResponse[list[MyApplicationItem]])
async def my_applications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[MyApplicationItem]]:
    apps = await application_service.list_my_applications(db, user)
    items = [
        MyApplicationItem.model_validate(
            {
                **{c.name: getattr(a, c.name) for c in a.__table__.columns},
                "room": RoomBriefForApplication.model_validate(a.room),
            }
        )
        for a in apps
    ]
    return APIResponse(data=items)


@router.post("/applications/{application_id}/cancel", response_model=APIResponse[ApplicationResponse])
async def cancel_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ApplicationResponse]:
    app = await application_service.cancel_my_application(db, user, application_id)
    await db.commit()
    await db.refresh(app)
    return APIResponse(data=ApplicationResponse.model_validate(app))


@router.get("/credits", response_model=APIResponse[CreditWallet])
async def my_credits(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[CreditWallet]:
    credits = await credit_service.list_my_credits(db, user.id)
    await db.commit()  # persists lazy "expired" status flips
    items = [CreditItem.model_validate(c) for c in credits]
    active = [c for c in credits if c.status == CreditStatus.ACTIVE.value]
    total_active_fixed = sum(
        (c.amount_krw or 0) for c in active if c.kind == CreditKind.FIXED_AMOUNT.value
    )
    has_percent = any(c.kind == CreditKind.PERCENT.value for c in active)
    return APIResponse(
        data=CreditWallet(
            active_count=len(active),
            expired_count=sum(1 for c in credits if c.status == CreditStatus.EXPIRED.value),
            used_count=sum(1 for c in credits if c.status == CreditStatus.USED.value),
            total_active_fixed_krw=int(total_active_fixed),
            has_percent_off=has_percent,
            items=items,
        )
    )


@router.get("/rooms", response_model=APIResponse[list[RoomListItem]])
async def my_confirmed_rooms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[RoomListItem]]:
    rooms = await application_service.list_my_confirmed_rooms(db, user)
    # Eager-load planner since to_list_item needs it.
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models import Room
    from app.services.room_service import to_list_item

    if rooms:
        ids = [r.id for r in rooms]
        rooms = list(
            (
                await db.scalars(
                    select(Room).options(selectinload(Room.planner)).where(Room.id.in_(ids))
                )
            ).all()
        )
    return APIResponse(data=[to_list_item(r) for r in rooms])
