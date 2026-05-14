import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import APIError, Conflict, Unauthorized
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models import RefreshToken, User
from app.models._enums import UserRole, UserStatus
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair


REFERRAL_ALPHABET = string.ascii_uppercase + string.digits  # 36^6 ≈ 2.18B
REFERRAL_CODE_LEN = 6


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _generate_referral_code(db: AsyncSession) -> str:
    """6-char alphanumeric, retried until unique. Collisions are astronomical."""
    for _ in range(8):
        code = "".join(secrets.choice(REFERRAL_ALPHABET) for _ in range(REFERRAL_CODE_LEN))
        exists = await db.scalar(select(User.id).where(User.referral_code == code))
        if exists is None:
            return code
    raise RuntimeError("Could not allocate unique referral code (extremely unlikely).")


async def _issue_token_pair(
    db: AsyncSession,
    user: User,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TokenPair:
    access = create_access_token(user.id, user.role)
    refresh = create_refresh_token(user.id)

    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_hash_refresh(refresh),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    await db.flush()
    return TokenPair(access_token=access, refresh_token=refresh)


async def register(db: AsyncSession, body: RegisterRequest) -> User:
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise Conflict("EMAIL_ALREADY_EXISTS", "An account with this email already exists.")

    if body.role == UserRole.ADMIN:
        raise Conflict("INVALID_ROLE", "Admin role cannot be created via registration.")

    # Resolve referrer (optional). Invalid code → soft error: still register.
    referred_by: User | None = None
    if body.referral_code:
        code = body.referral_code.upper().strip()
        referred_by = await db.scalar(select(User).where(User.referral_code == code))
        if referred_by is None:
            raise APIError(
                "INVALID_REFERRAL_CODE",
                "추천 코드가 유효하지 않습니다.",
                status_code=409,
            )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role.value,
        status=UserStatus.ACTIVE.value,
        referral_code=await _generate_referral_code(db),
        referred_by_user_id=referred_by.id if referred_by else None,
    )
    db.add(user)
    await db.flush()
    return user


async def login(
    db: AsyncSession,
    body: LoginRequest,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[User, TokenPair]:
    user = await db.scalar(select(User).where(User.email == body.email))
    if user is None or user.password_hash is None:
        raise Unauthorized("Invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise Unauthorized("Invalid credentials")
    if user.status != UserStatus.ACTIVE.value:
        raise Unauthorized(f"Account is {user.status}")

    user.last_login_at = datetime.now(timezone.utc)
    pair = await _issue_token_pair(db, user, user_agent=user_agent, ip_address=ip_address)
    return user, pair


async def refresh(
    db: AsyncSession,
    refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> TokenPair:
    try:
        payload = decode_token(refresh_token)
    except ValueError as exc:
        raise Unauthorized(str(exc)) from exc
    if payload.get("type") != "refresh":
        raise Unauthorized("Wrong token type")

    sub = payload.get("sub")
    if not sub:
        raise Unauthorized("Invalid token payload")

    try:
        user_id = UUID(sub)
    except (TypeError, ValueError) as exc:
        raise Unauthorized("Invalid user identifier") from exc

    token_hash = _hash_refresh(refresh_token)
    stored = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.token_hash == token_hash,
        )
    )
    if stored is None or stored.revoked:
        raise Unauthorized("Refresh token not recognized")
    if stored.expires_at <= datetime.now(timezone.utc):
        raise Unauthorized("Refresh token expired")

    user = await db.scalar(select(User).where(User.id == user_id))
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise Unauthorized("User unavailable")

    # Rotate: revoke the used token and issue a new pair.
    stored.revoked = True
    stored.revoked_at = datetime.now(timezone.utc)
    pair = await _issue_token_pair(db, user, user_agent=user_agent, ip_address=ip_address)
    return pair


async def logout(db: AsyncSession, user_id: UUID) -> None:
    tokens = (
        await db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False)
            )
        )
    ).all()
    now = datetime.now(timezone.utc)
    for t in tokens:
        t.revoked = True
        t.revoked_at = now
