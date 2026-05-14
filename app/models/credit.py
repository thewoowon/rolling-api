import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._enums import CreditKind, CreditStatus, CreditSource
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Credit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A discount / cashback granted to a user.

    Two kinds:
    - `fixed_amount`: subtract `amount_krw` won from next applicable payment
    - `percent`: discount `percent_off` % capped at `max_discount_krw`

    Lifecycle: ACTIVE -> USED (applied to an application) | EXPIRED | VOIDED.
    """

    __tablename__ = "credits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_krw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    percent_off: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_discount_krw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=CreditStatus.ACTIVE.value, index=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_room_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_on_application_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("room_applications.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


__all__ = ["Credit", "CreditKind", "CreditStatus", "CreditSource"]
