import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._enums import RotationRoundStatus
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RotationRound(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rotation_rounds"
    __table_args__ = (
        UniqueConstraint("session_id", "round_number", name="uq_rotation_round_session_number"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("rotation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RotationRoundStatus.PENDING.value
    )

    session: Mapped["RotationSession"] = relationship("RotationSession", back_populates="rounds")
    seat_assignments: Mapped[list["SeatAssignment"]] = relationship(
        "SeatAssignment", back_populates="round", cascade="all, delete-orphan"
    )
