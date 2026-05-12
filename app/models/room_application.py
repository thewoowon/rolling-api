import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._enums import ApplicationStatus
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RoomApplication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "room_applications"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_application_room_user"),)

    room_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=ApplicationStatus.SUBMITTED.value, index=True
    )
    applicant_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    planner_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    room: Mapped["Room"] = relationship("Room", back_populates="applications")
