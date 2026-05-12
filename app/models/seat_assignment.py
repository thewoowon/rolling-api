import uuid

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SeatAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "seat_assignments"

    room_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("rotation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("rotation_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_a_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    participant_b_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    table_number: Mapped[int] = mapped_column(Integer, nullable=False)

    round: Mapped["RotationRound"] = relationship("RotationRound", back_populates="seat_assignments")
