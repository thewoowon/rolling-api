"""Credits = discount / cashback awarded to a user.

Two kinds:
- `fixed_amount`: subtract `amount_krw` won from next applicable payment
- `percent`: discount `percent_off` % capped at `max_discount_krw`

Three sources, all automatic:
- VIABLE_HOST_BONUS — host's room reached VIABLE; emits 30% off (cap 10,000원), 90d
- REFERRAL_HOST — referred friend completed their first CONFIRMED application; emits 3,000원 fixed, 90d
- REFERRAL_FRIEND — friend signed up with referral code; emits 3,000원 fixed first-room discount, 90d

Anti-abuse for v1: simple rules. Detect on-demand via admin dashboards.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Credit, User
from app.models._enums import CreditKind, CreditSource, CreditStatus


# Limits — tweak via config later.
DEFAULT_EXPIRY_DAYS = 90
VIABLE_HOST_PERCENT = 30
VIABLE_HOST_MAX_KRW = 10_000
REFERRAL_HOST_AMOUNT_KRW = 3_000
REFERRAL_FRIEND_AMOUNT_KRW = 3_000
MAX_REFERRAL_BONUSES_PER_HOST = 5


def _expiry_at(days: int = DEFAULT_EXPIRY_DAYS) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=days)


# ---- issuing ----------------------------------------------------------------


async def issue_viable_host_bonus(
    db: AsyncSession, host_user_id: UUID, room_id: UUID
) -> Credit | None:
    """Issue once per (host, room). Idempotent."""
    existing = await db.scalar(
        select(Credit).where(
            Credit.user_id == host_user_id,
            Credit.source == CreditSource.VIABLE_HOST_BONUS.value,
            Credit.source_room_id == room_id,
        )
    )
    if existing is not None:
        return existing

    credit = Credit(
        user_id=host_user_id,
        kind=CreditKind.PERCENT.value,
        percent_off=VIABLE_HOST_PERCENT,
        max_discount_krw=VIABLE_HOST_MAX_KRW,
        status=CreditStatus.ACTIVE.value,
        source=CreditSource.VIABLE_HOST_BONUS.value,
        source_room_id=room_id,
        expires_at=_expiry_at(),
        description=f"방 성립 보상 — {VIABLE_HOST_PERCENT}% 할인 (최대 {VIABLE_HOST_MAX_KRW:,}원)",
    )
    db.add(credit)
    await db.flush()
    return credit


async def issue_referral_pair(
    db: AsyncSession, referrer_id: UUID, friend_id: UUID
) -> tuple[Credit | None, Credit | None]:
    """Award both sides of a successful referral. Called once when the friend
    completes their FIRST CONFIRMED application.

    Caps the referrer's lifetime bonuses at MAX_REFERRAL_BONUSES_PER_HOST.
    Idempotent — if either side already emitted for this pair, returns existing.
    """
    # Already paid out for this (referrer, friend) pair?
    existing_referrer = await db.scalar(
        select(Credit).where(
            Credit.user_id == referrer_id,
            Credit.source == CreditSource.REFERRAL_HOST.value,
            Credit.source_user_id == friend_id,
        )
    )
    if existing_referrer is not None:
        return existing_referrer, None

    # Cap check
    count = (
        await db.scalar(
            select(func.count())
            .select_from(Credit)
            .where(
                Credit.user_id == referrer_id,
                Credit.source == CreditSource.REFERRAL_HOST.value,
            )
        )
    ) or 0
    if count >= MAX_REFERRAL_BONUSES_PER_HOST:
        return None, None

    referrer_credit = Credit(
        user_id=referrer_id,
        kind=CreditKind.FIXED_AMOUNT.value,
        amount_krw=REFERRAL_HOST_AMOUNT_KRW,
        status=CreditStatus.ACTIVE.value,
        source=CreditSource.REFERRAL_HOST.value,
        source_user_id=friend_id,
        expires_at=_expiry_at(),
        description=f"친구 추천 보상 — {REFERRAL_HOST_AMOUNT_KRW:,}원 크레딧",
    )
    friend_credit = Credit(
        user_id=friend_id,
        kind=CreditKind.FIXED_AMOUNT.value,
        amount_krw=REFERRAL_FRIEND_AMOUNT_KRW,
        status=CreditStatus.ACTIVE.value,
        source=CreditSource.REFERRAL_FRIEND.value,
        source_user_id=referrer_id,
        expires_at=_expiry_at(),
        description=f"가입 환영 — 첫 방 {REFERRAL_FRIEND_AMOUNT_KRW:,}원 할인",
    )
    db.add(referrer_credit)
    db.add(friend_credit)
    await db.flush()
    return referrer_credit, friend_credit


# ---- reading ----------------------------------------------------------------


async def list_my_credits(db: AsyncSession, user_id: UUID) -> list[Credit]:
    rows = (
        await db.scalars(
            select(Credit)
            .where(Credit.user_id == user_id)
            .order_by(Credit.created_at.desc())
        )
    ).all()
    # Side-effect: mark expired credits lazily.
    now = datetime.now(timezone.utc)
    for c in rows:
        if c.status == CreditStatus.ACTIVE.value and c.expires_at <= now:
            c.status = CreditStatus.EXPIRED.value
    if any(c.status == CreditStatus.EXPIRED.value for c in rows):
        await db.flush()
    return list(rows)


async def active_credits(db: AsyncSession, user_id: UUID) -> list[Credit]:
    now = datetime.now(timezone.utc)
    return list(
        (
            await db.scalars(
                select(Credit).where(
                    Credit.user_id == user_id,
                    Credit.status == CreditStatus.ACTIVE.value,
                    Credit.expires_at > now,
                )
            )
        ).all()
    )


def estimate_discount(credit: Credit, price_amount: int) -> int:
    """Compute discount won for a credit applied to a given price."""
    if credit.kind == CreditKind.FIXED_AMOUNT.value:
        return min(credit.amount_krw or 0, price_amount)
    if credit.kind == CreditKind.PERCENT.value and credit.percent_off:
        raw = int(price_amount * credit.percent_off / 100)
        if credit.max_discount_krw is not None:
            raw = min(raw, credit.max_discount_krw)
        return min(raw, price_amount)
    return 0


def best_discount(credits: list[Credit], price_amount: int) -> tuple[Credit | None, int]:
    """Pick the credit that yields the biggest discount for this price."""
    best: tuple[Credit | None, int] = (None, 0)
    for c in credits:
        d = estimate_discount(c, price_amount)
        if d > best[1]:
            best = (c, d)
    return best


async def credit_summary(db: AsyncSession, user_id: UUID, price_amount: int) -> dict:
    """For the room detail page: 'you have X credits worth up to Y won off this room'."""
    actives = await active_credits(db, user_id)
    best, discount = best_discount(actives, price_amount)
    return {
        "active_count": len(actives),
        "best_discount_krw": discount,
        "best_credit_id": str(best.id) if best else None,
        "best_credit_description": best.description if best else None,
    }
