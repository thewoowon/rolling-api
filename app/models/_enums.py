from enum import StrEnum


class UserRole(StrEnum):
    PARTICIPANT = "participant"
    PLANNER = "planner"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    WITHDRAWN = "withdrawn"


class PlannerStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    SUSPENDED = "suspended"


class RoomStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RECRUITING = "recruiting"
    VIABLE = "viable"
    ASSIGNED = "assigned"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RoomType(StrEnum):
    THREE_BY_THREE = "three_by_three"
    FOUR_BY_FOUR = "four_by_four"
    SIX_BY_SIX = "six_by_six"
    OFFLINE_PARTY = "offline_party"
    THEME_BASED = "theme_based"


class RoomVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class ApplicationStatus(StrEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    WAITLISTED = "waitlisted"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class PaymentType(StrEnum):
    PARTICIPATION_FEE = "participation_fee"
    DEPOSIT = "deposit"
    REFUND = "refund"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUND_REQUESTED = "refund_requested"
    REFUNDED = "refunded"


class CheckInStatus(StrEnum):
    NOT_OPEN = "not_open"
    OPEN = "open"
    CHECKED_IN = "checked_in"
    NO_SHOW = "no_show"


class RotationSessionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class RotationRoundStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"


class ChoiceType(StrEnum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    MAYBE = "maybe"


class MatchStatus(StrEnum):
    PENDING = "pending"
    MUTUAL = "mutual"
    ONE_SIDED = "one_sided"
    NONE = "none"
    AFTER_PROPOSED = "after_proposed"
    AFTER_CONFIRMED = "after_confirmed"
    CLOSED = "closed"


class AfterDateProposalStatus(StrEnum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class ReportStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class CreditKind(StrEnum):
    FIXED_AMOUNT = "fixed_amount"  # discrete amount in KRW
    PERCENT = "percent"  # discount percentage with optional cap


class CreditStatus(StrEnum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    VOIDED = "voided"


class CreditSource(StrEnum):
    VIABLE_HOST_BONUS = "viable_host_bonus"
    REFERRAL_HOST = "referral_host"
    REFERRAL_FRIEND = "referral_friend"
    MANUAL_GRANT = "manual_grant"
