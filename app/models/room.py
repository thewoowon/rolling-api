import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._enums import RoomStatus, RoomVisibility
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Room(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rooms"

    # Host = the user who created and owns this room. Always required.
    host_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Planner = the Rolling-affiliated operator assigned later from the queue.
    # Nullable until admin assigns from the VIABLE queue.
    planner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("planners.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RoomStatus.DRAFT.value, index=True
    )
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    venue_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    venue_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    min_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    male_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    female_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deposit_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="KRW")
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(30), nullable=False, default=RoomVisibility.PUBLIC.value
    )
    # When the room reaches viability and enters the admin assignment queue.
    viable_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    planner: Mapped["Planner | None"] = relationship("Planner", back_populates="rooms")
    applications: Mapped[list["RoomApplication"]] = relationship(
        "RoomApplication", back_populates="room", cascade="all, delete-orphan"
    )
