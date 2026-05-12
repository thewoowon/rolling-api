from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import decode_token
from app.models import User
from app.models._enums import UserRole, UserStatus
from sqlalchemy import select


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


def _extract_bearer(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise Unauthorized("Missing bearer token")
    return header.split(" ", 1)[1].strip()


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = _extract_bearer(request)
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise Unauthorized(str(exc)) from exc

    if payload.get("type") != "access":
        raise Unauthorized("Wrong token type")

    sub = payload.get("sub")
    if not sub:
        raise Unauthorized("Invalid token payload")

    try:
        user_id = UUID(sub)
    except (TypeError, ValueError) as exc:
        raise Unauthorized("Invalid user identifier") from exc

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise Unauthorized("User not found")
    if user.status != UserStatus.ACTIVE.value:
        raise Forbidden(f"Account is {user.status}")
    return user


def require_roles(*roles: UserRole):
    allowed = {r.value for r in roles}

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise Forbidden(f"Requires role: {','.join(sorted(allowed))}")
        return user

    return dependency
