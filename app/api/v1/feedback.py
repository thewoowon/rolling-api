from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import APIResponse
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services import feedback_service

router = APIRouter()


@router.post(
    "/rooms/{room_id}/feedback",
    response_model=APIResponse[FeedbackResponse],
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    room_id: UUID,
    body: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[FeedbackResponse]:
    fb = await feedback_service.submit_feedback(db, user, room_id, body)
    await db.commit()
    await db.refresh(fb)
    return APIResponse(data=FeedbackResponse.model_validate(fb))
