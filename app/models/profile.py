import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Profile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    birth_year: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    education: Mapped[str | None] = mapped_column(String(100), nullable=True)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smoking: Mapped[str | None] = mapped_column(String(30), nullable=True)
    drinking: Mapped[str | None] = mapped_column(String(30), nullable=True)
    religion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relationship_intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    friend_intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profile_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="profile")
