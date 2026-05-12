from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.choice import (
    AfterDateProposalCreate,
    AfterDateProposalResponse,
    ChoiceSubmission,
    ChoiceSubmissionResult,
    ChoiceTarget,
    MatchSummary,
)
from app.schemas.common import APIResponse
from app.services import choice_service

router = APIRouter()


@router.get(
    "/rooms/{room_id}/choice-targets",
    response_model=APIResponse[list[ChoiceTarget]],
)
async def list_choice_targets(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[ChoiceTarget]]:
    targets = await choice_service.list_choice_targets(db, user, room_id)
    return APIResponse(data=targets)


@router.post(
    "/rooms/{room_id}/choices",
    response_model=APIResponse[ChoiceSubmissionResult],
    status_code=status.HTTP_201_CREATED,
)
async def submit_choices(
    room_id: UUID,
    body: ChoiceSubmission,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ChoiceSubmissionResult]:
    accepted, new_mutual = await choice_service.submit_choices(
        db, user, room_id, body.choices
    )
    await db.commit()
    return APIResponse(
        data=ChoiceSubmissionResult(
            accepted=accepted, new_mutual_matches=new_mutual
        )
    )


@router.get(
    "/rooms/{room_id}/my-matches",
    response_model=APIResponse[list[MatchSummary]],
)
async def my_matches(
    room_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[list[MatchSummary]]:
    matches = await choice_service.list_my_matches(db, user, room_id)
    return APIResponse(data=matches)


@router.post(
    "/matches/{match_id}/after-date-proposals",
    response_model=APIResponse[AfterDateProposalResponse],
    status_code=status.HTTP_201_CREATED,
)
async def propose_after_date(
    match_id: UUID,
    body: AfterDateProposalCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[AfterDateProposalResponse]:
    proposal = await choice_service.propose_after_date(db, user, match_id, body)
    await db.commit()
    return APIResponse(data=proposal)
