from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.common import APIResponse

router = APIRouter()


@router.get("/health", response_model=APIResponse[dict])
async def health(db: AsyncSession = Depends(get_db)) -> APIResponse[dict]:
    db_ok = False
    try:
        result = await db.execute(text("SELECT 1"))
        db_ok = result.scalar() == 1
    except Exception:
        db_ok = False
    return APIResponse(
        data={
            "status": "ok" if db_ok else "degraded",
            "db": db_ok,
            "time": datetime.now(timezone.utc).isoformat(),
        }
    )
