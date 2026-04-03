from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    BUSINESS = "business"
    DRIVER = "driver"
    RIDER = "rider"
    FACILITY = "facility"


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


class FleetApplicationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MORE_INFO_REQUESTED = "more_info_requested"


class VehicleStatus(StrEnum):
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    INACTIVE = "inactive"


class VehicleCategory(StrEnum):
    STANDARD = "standard"
    WHEELCHAIR_ACCESSIBLE = "wheelchair_accessible"
    ASSISTED_RIDE = "assisted_ride"
    STRETCHER_TRANSPORT = "stretcher_transport"


class FleetDocumentType(StrEnum):
    BUSINESS_LICENSE = "business_license"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    VEHICLE_FLEET_LIST = "vehicle_fleet_list"
    DRIVER_CERTIFICATIONS = "driver_certifications"
    OTHER = "other"


class RefundRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RefundCategory(StrEnum):
    DRIVER_NO_SHOW = "driver_no_show"
    WRONG_PICKUP = "wrong_pickup"
    SERVICE_ISSUE = "service_issue"
    OVERCHARGED = "overcharged"
    CANCELLED_BY_SYSTEM = "cancelled_by_system"
    OTHER = "other"


class CaregiverSpecialty(StrEnum):
    PSW = "psw"
    RPN = "rpn"
    RN = "rn"
    HCA = "hca"
    PARAMEDIC = "paramedic"
    OTHER = "other"


class PayoutStatus(StrEnum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    FAILED = "failed"


class DriverAccountStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class ServiceCapability(StrEnum):
    AMBULATORY = "ambulatory"
    WHEELCHAIR = "wheelchair"
    STRETCHER = "stretcher"


class VehicleDocumentType(StrEnum):
    REGISTRATION = "registration"
    INSURANCE_CERTIFICATE = "insurance_certificate"
    SAFETY_INSPECTION = "safety_inspection"


class VehicleDocumentStatus(StrEnum):
    VALID = "valid"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    MISSING = "missing"


class RiderAccountStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"


class RiderIssueStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"


class RiderIssueType(StrEnum):
    SUPPORT_TICKET = "support_ticket"
    COMPLAINT = "complaint"
    REFUND_REQUEST = "refund_request"
    NO_SHOW = "no_show"
    APP_ISSUE = "app_issue"
    VEHICLE_COMPLAINT = "vehicle_complaint"


class RiderIssuePriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Phase 12: Safety & Incidents + Admin Notifications ──


class IncidentType(StrEnum):
    DRIVER_COMPLAINT = "driver_complaint"
    RIDER_COMPLAINT = "rider_complaint"
    ACCIDENT = "accident"


class IncidentSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(StrEnum):
    UNDER_INVESTIGATION = "under_investigation"
    DISCIPLINARY_ACTION = "disciplinary_action"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AlertCategory(StrEnum):
    ROUTE_DEVIATION = "route_deviation"
    LATE_ARRIVAL = "late_arrival"
    UNEXPECTED_STOP = "unexpected_stop"
    SPEED_VIOLATION = "speed_violation"
    IDLE_VEHICLE = "idle_vehicle"


class AlertSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class InvestigationStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    UNASSIGNED = "unassigned"
    COMPLETED = "completed"
    CLOSED = "closed"


class DisciplinaryActionType(StrEnum):
    ACCOUNT_SUSPENSION = "account_suspension"
    DRIVING_SUSPENSION = "driving_suspension"
    WRITTEN_WARNING = "written_warning"


class DisciplinaryActionStatus(StrEnum):
    ACTIVE = "active"
    ISSUED = "issued"
    EXPIRED = "expired"
    REINSTATED = "reinstated"


class BroadcastType(StrEnum):
    SYSTEM = "system"
    RIDER = "rider"
    DRIVER = "driver"
    FLEET = "fleet"


class BroadcastNotificationType(StrEnum):
    # System
    MAINTENANCE = "maintenance"
    SECURITY_ALERT = "security_alert"
    PLATFORM_UPDATE = "platform_update"
    POLICY_CHANGE = "policy_change"
    # Rider
    ANNOUNCEMENT = "announcement"
    PROMOTION = "promotion"
    SERVICE_UPDATE = "service_update"
    FEATURE_LAUNCH = "feature_launch"
    # Driver
    SURGE_ALERT = "surge_alert"
    PAYOUT_NOTICE = "payout_notice"
    TRAINING_UPDATE = "training_update"
    COMPLIANCE_REMINDER = "compliance_reminder"
    # Fleet
    REVENUE_REPORT = "revenue_report"
    FLEET_POLICY_UPDATE = "fleet_policy_update"
    VEHICLE_ALERT = "vehicle_alert"
    PARTNERSHIP_UPDATE = "partnership_update"


# ── Phase 13: Support & Service + System Logs ──


class SupportTicketType(StrEnum):
    RIDER_COMPLAINT = "rider_complaint"
    DRIVER_COMPLAINT = "driver_complaint"
    RIDE_DISPUTE = "ride_dispute"


class SupportTicketStatus(StrEnum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"


class ContactChannel(StrEnum):
    PHONE_CALL = "phone_call"
    LIVE_CHAT = "live_chat"
    EMAIL = "email"


class ContactRole(StrEnum):
    RIDER = "rider"
    DRIVER = "driver"
    FLEET_PARTNER = "fleet_partner"


class ActivityLogCategory(StrEnum):
    ADMIN = "admin"
    FLEET = "fleet"
    DRIVER = "driver"
    FINANCE = "finance"
    SUPPORT = "support"
    SETTINGS = "settings"
    SAFETY = "safety"
    NOTIFICATION = "notification"
    BOOKING = "booking"
    DISPATCH = "dispatch"


class ActivityLogSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class LoginStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class FacilityType(StrEnum):
    HOSPITAL = "hospital"
    CARE_HOME = "care_home"
    REHAB_CENTER = "rehab_center"


class BookingChannel(StrEnum):
    MOBILE_APP = "mobile_app"
    WEBSITE_CLIENT = "website_client"
    WEBSITE_FACILITY = "website_facility"
