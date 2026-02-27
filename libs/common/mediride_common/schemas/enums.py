from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    BUSINESS = "business"
    DRIVER = "driver"
    RIDER = "rider"


class RideStatus(StrEnum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    DRIVER_ASSIGNED = "driver_assigned"
    DRIVER_EN_ROUTE = "driver_en_route"
    DRIVER_ARRIVED = "driver_arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class RideType(StrEnum):
    STANDARD = "standard"
    WHEELCHAIR = "wheelchair"
    STRETCHER = "stretcher"


class TripType(StrEnum):
    TRANSPORT_ONLY = "transport_only"
    TRANSPORT_ESCORT = "transport_escort"


class TripStructure(StrEnum):
    ONE_WAY = "one_way"
    ROUND_TRIP = "round_trip"


class VisitType(StrEnum):
    MOBILE = "mobile"
    CHECKUP = "checkup"
    THERAPY = "therapy"
    LAB_RIDE = "lab_ride"
    SURGERY = "surgery"
    OTHER = "other"


class MobilityLevel(StrEnum):
    AMBULATORY = "ambulatory"
    WHEELCHAIR = "wheelchair"
    STRETCHER = "stretcher"


class AssistanceLevel(StrEnum):
    NONE = "none"
    MINIMAL = "minimal"
    MODERATE = "moderate"
    FULL = "full"


class LocationType(StrEnum):
    HOME = "home"
    WORK = "work"
    MEDICAL = "medical"
    CUSTOM = "custom"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class OTPPurpose(StrEnum):
    REGISTRATION = "registration"
    LOGIN = "login"
    PASSWORD_RESET = "password_reset"


class OTPChannel(StrEnum):
    EMAIL = "email"
    SMS = "sms"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class BackgroundCheckStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"


class RecurringFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
