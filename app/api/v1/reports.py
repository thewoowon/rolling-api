from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.common import APIResponse
from app.schemas.report import ReportCreate, ReportResponse
from app.services import report_service

router = APIRouter()


@router.post(
    "",
    response_model=APIResponse[ReportResponse],
    status_code=status.HTTP_201_CREATED,
)
async def submit_report(
    body: ReportCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[ReportResponse]:
    report = await report_service.submit_report(db, user, body)
    await db.commit()
    await db.refresh(report)
    return APIResponse(data=ReportResponse.model_validate(report))
