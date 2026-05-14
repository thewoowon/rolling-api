import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._enums import UserRole, UserStatus
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(
        String(30), nullable=False, default=UserRole.PARTICIPANT.value
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=UserStatus.ACTIVE.value
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 6-character alphanumeric, unique. Generated on registration; nullable for
    # legacy rows backfilled in migration.
    referral_code: Mapped[str | None] = mapped_column(
        String(8), unique=True, nullable=True, index=True
    )
    # The user who referred this one (their code was used at signup).
    referred_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Track whether the referral bonus has already been emitted (to prevent
    # duplicate awards if the referred user pays for multiple rooms).
    referral_bonus_emitted: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )

    profile: Mapped["Profile | None"] = relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    planner: Mapped["Planner | None"] = relationship(
        "Planner", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
