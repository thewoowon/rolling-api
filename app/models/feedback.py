import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Feedback(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating_range"),
        CheckConstraint(
            "safety_rating IS NULL OR safety_rating BETWEEN 1 AND 5",
            name="ck_feedback_safety_range",
        ),
        CheckConstraint(
            "planner_rating IS NULL OR planner_rating BETWEEN 1 AND 5",
            name="ck_feedback_planner_range",
        ),
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planner_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    would_join_again: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
