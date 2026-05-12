import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._enums import CheckInStatus
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CheckIn(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "check_ins"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_checkin_room_user"),)

    room_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("room_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=CheckInStatus.NOT_OPEN.value
    )
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_in_code: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
