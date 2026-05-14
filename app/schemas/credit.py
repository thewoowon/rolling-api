from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models._enums import CreditKind, CreditSource, CreditStatus


class CreditItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: CreditKind
    amount_krw: int | None
    percent_off: int | None
    max_discount_krw: int | None
    status: CreditStatus
    source: CreditSource
    expires_at: datetime
    used_at: datetime | None
    description: str | None
    created_at: datetime


class CreditWallet(BaseModel):
    """Aggregate view for `/me/credits`."""

    active_count: int
    expired_count: int
    used_count: int
    total_active_fixed_krw: int
    has_percent_off: bool
    items: list[CreditItem]


class CreditSummary(BaseModel):
    """For room detail page: 'you have X discount available for this price'."""

    active_count: int
    best_discount_krw: int
    best_credit_id: UUID | None
    best_credit_description: str | None
