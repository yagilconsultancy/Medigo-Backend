from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    BUSINESS = "business"
    DRIVER = "driver"
    RIDER = "rider"


class RideStatus(StrEnum):
    REQUESTED = "requested"
    PENDING_BUSINESS_ASSIGNMENT = "pending_business_assignment"
    CONFIRMED = "confirmed"
    DRIVER_ASSIGNED = "driver_assigned"
    DRIVER_EN_ROUTE = "driver_en_route"
    DRIVER_ARRIVED = "driver_arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class RideType(StrEnum):
    AMBULATORY = "ambulatory"
    STANDARD = "standard"  # Deprecated: use AMBULATORY
    WHEELCHAIR = "wheelchair"
    STRETCHER = "stretcher"


class TripType(StrEnum):
    TRANSPORT_ONLY = "transport_only"
    TRANSPORT_CARE_ASSISTANT = "transport_care_assistant"
    TRANSPORT_ESCORT = "transport_escort"  # Deprecated: use TRANSPORT_CARE_ASSISTANT


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


class CancellationReason(StrEnum):
    RIDER_CANCELLED = "rider_cancelled"
    DRIVER_CANCELLED = "driver_cancelled"
    NO_SHOW = "no_show"
    EMERGENCY = "emergency"
    SYSTEM = "system"


class RideRequestStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class RatingType(StrEnum):
    DRIVER_TO_RIDER = "driver_to_rider"
    RIDER_TO_DRIVER = "rider_to_driver"


class WithdrawalStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentMethodType(StrEnum):
    BANK_ACCOUNT = "bank_account"
    DEBIT_CARD = "debit_card"


class TransactionType(StrEnum):
    RIDE_PAYMENT = "ride_payment"
    WITHDRAWAL = "withdrawal"
    PLATFORM_FEE = "platform_fee"
    TIP = "tip"
    BONUS = "bonus"
    REFUND = "refund"


class NotificationType(StrEnum):
    RIDE_UPDATE = "ride_update"
    RIDE_REMINDER = "ride_reminder"
    PAYMENT = "payment"
    CHAT = "chat"
    SYSTEM = "system"
    PROMOTION = "promotion"


class TrackingSessionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class MessageType(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    SYSTEM = "system"


class BusinessAssignmentStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
