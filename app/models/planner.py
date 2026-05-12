import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._enums import PlannerStatus
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Planner(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "planners"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=PlannerStatus.PENDING.value
    )
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    total_rooms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship("User", back_populates="planner")
    # Rooms this planner is currently assigned to. Planner deletion sets FK to NULL,
    # so cascade-delete is not appropriate here.
    rooms: Mapped[list["Room"]] = relationship("Room", back_populates="planner")
