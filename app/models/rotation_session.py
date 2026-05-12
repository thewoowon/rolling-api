import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._enums import RotationSessionStatus
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RotationSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rotation_sessions"

    room_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RotationSessionStatus.PENDING.value
    )
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    round_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rounds: Mapped[list["RotationRound"]] = relationship(
        "RotationRound", back_populates="session", cascade="all, delete-orphan"
    )
