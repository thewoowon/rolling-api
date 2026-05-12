import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MatchResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "match_results"
    __table_args__ = (
        UniqueConstraint("room_id", "user_a_id", "user_b_id", name="uq_match_room_users"),
        CheckConstraint("user_a_id <> user_b_id", name="ck_match_self"),
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_a_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_b_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    after_proposals: Mapped[list["AfterDateProposal"]] = relationship(
        "AfterDateProposal", back_populates="match_result", cascade="all, delete-orphan"
    )
