import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._enums import AfterDateProposalStatus
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AfterDateProposal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "after_date_proposals"

    match_result_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("match_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    proposed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    proposed_place: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=AfterDateProposalStatus.PROPOSED.value
    )

    match_result: Mapped["MatchResult"] = relationship("MatchResult", back_populates="after_proposals")
