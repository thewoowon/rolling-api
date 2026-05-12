from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models._enums import UserRole
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.common import APIResponse
from app.services import auth_service

router = APIRouter()


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip() or ip
    return ua, ip


@router.post(
    "/register",
    response_model=APIResponse[MeResponse],
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[MeResponse]:
    user = await auth_service.register(db, body)
    await db.commit()
    return APIResponse(
        data=MeResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            role=UserRole(user.role),
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )
    )


@router.post("/login", response_model=APIResponse[TokenPair])
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[TokenPair]:
    ua, ip = _client_meta(request)
    _user, pair = await auth_service.login(db, body, user_agent=ua, ip_address=ip)
    await db.commit()
    return APIResponse(data=pair)


@router.post("/refresh", response_model=APIResponse[TokenPair])
async def refresh(
    body: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[TokenPair]:
    ua, ip = _client_meta(request)
    pair = await auth_service.refresh(db, body.refresh_token, user_agent=ua, ip_address=ip)
    await db.commit()
    return APIResponse(data=pair)


@router.post("/logout", response_model=APIResponse[dict])
async def logout(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    await auth_service.logout(db, user.id)
    await db.commit()
    return APIResponse(data={"ok": True})


@router.get("/me", response_model=APIResponse[MeResponse])
async def me(user: User = Depends(get_current_user)) -> APIResponse[MeResponse]:
    return APIResponse(
        data=MeResponse(
            id=user.id,
            email=user.email,
            phone=user.phone,
            role=UserRole(user.role),
            status=user.status,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
        )
    )
