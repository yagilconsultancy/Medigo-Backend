class Exchanges:
    AUTH = "mediride.auth"
    USERS = "mediride.users"
    RIDES = "mediride.rides"
    PAYMENTS = "mediride.payments"
    TRACKING = "mediride.tracking"
    CHAT = "mediride.chat"
    DLX = "mediride.dlx"


class RoutingKeys:
    # Auth events
    USER_REGISTERED = "user.registered"
    USER_VERIFIED = "user.verified"
    USER_OTP_REQUESTED = "user.otp_requested"
    USER_LOGIN = "user.login"
    USER_PASSWORD_CHANGED = "user.password_changed"
    PASSWORD_RESET_REQUESTED = "user.password_reset_requested"
    DRIVER_INVITE_SENT = "driver.invite.sent"
    ADMIN_INVITE_SENT = "admin.invite.sent"

    # User events
    PROFILE_CREATED = "profile.created"
    PROFILE_UPDATED = "profile.updated"
    DRIVER_APPROVED = "driver.approved"
    DRIVER_SUSPENDED = "driver.suspended"
    DRIVER_ONLINE = "driver.online"
    DRIVER_OFFLINE = "driver.offline"
    FLEET_CREATED = "fleet.created"
    FLEET_UPDATED = "fleet.updated"
    DRIVER_DOCUMENT_UPLOADED = "driver.document.uploaded"

    # Ride events
    RIDE_CREATED = "ride.created"
    RIDE_CONFIRMED = "ride.confirmed"
    RIDE_DRIVER_ASSIGNED = "ride.driver_assigned"
    RIDE_DRIVER_UNASSIGNED = "ride.driver_unassigned"
    RIDE_DRIVER_EN_ROUTE = "ride.driver_en_route"
    RIDE_DRIVER_ARRIVED = "ride.driver_arrived"
    RIDE_IN_PROGRESS = "ride.in_progress"
    RIDE_COMPLETED = "ride.completed"
    RIDE_CANCELLED = "ride.cancelled"
    RIDE_NO_SHOW = "ride.no_show"
    RIDE_REQUEST_SENT = "ride.request.sent"
    RIDE_REQUEST_ACCEPTED = "ride.request.accepted"
    RIDE_REQUEST_DECLINED = "ride.request.declined"

    # Rating events
    RIDE_RATING_SUBMITTED = "ride.rating.submitted"

    # Payment events
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    EARNINGS_CALCULATED = "earnings.calculated"
    WITHDRAWAL_REQUESTED = "withdrawal.requested"
    WITHDRAWAL_COMPLETED = "withdrawal.completed"
    WITHDRAWAL_FAILED = "withdrawal.failed"

    # Tracking events
    DRIVER_LOCATION_UPDATED = "driver.location.updated"
    RIDE_ETA_UPDATED = "ride.eta.updated"

    # Chat events
    CHAT_MESSAGE_SENT = "chat.message.sent"
    CHAT_MESSAGE_READ = "chat.message.read"

    # Refund events
    REFUND_REQUEST_CREATED = "refund.request.created"
    REFUND_REQUEST_APPROVED = "refund.request.approved"
    REFUND_REQUEST_REJECTED = "refund.request.rejected"

    # Dispute events
    DISPUTE_CREATED = "dispute.created"
    DISPUTE_APPROVED = "dispute.approved"
    DISPUTE_REJECTED = "dispute.rejected"

    # Payout events
    PAYOUT_INITIATED = "payout.initiated"
    PAYOUT_COMPLETED = "payout.completed"
    PAYOUT_FAILED = "payout.failed"

    # Fleet events
    FLEET_APPLICATION_CREATED = "fleet.application.created"
    FLEET_APPLICATION_APPROVED = "fleet.application.approved"
    FLEET_APPLICATION_REJECTED = "fleet.application.rejected"
    FLEET_APPLICATION_INFO_REQUESTED = "fleet.application.info_requested"
    FLEET_STATUS_CHANGED = "fleet.status.changed"
    FLEET_VEHICLE_CREATED = "fleet.vehicle.created"
    FLEET_VEHICLE_STATUS_CHANGED = "fleet.vehicle.status_changed"
    FLEET_VEHICLE_MAINTENANCE_SCHEDULED = "fleet.vehicle.maintenance_scheduled"
    VEHICLE_DOCUMENT_UPLOADED = "fleet.vehicle.document.uploaded"
    VEHICLE_DOCUMENT_REPLACED = "fleet.vehicle.document.replaced"
    VEHICLE_CATEGORY_UPDATED = "fleet.vehicle.category.updated"

    # Driver management events
    DRIVER_ACCOUNT_CREATED = "driver.account.created"
    DRIVER_REACTIVATED = "driver.reactivated"
    DRIVER_DEACTIVATED = "driver.deactivated"
    DRIVER_PROFILE_UPDATED = "driver.profile.updated"

    # Rider management events
    RIDER_SUSPENDED = "rider.suspended"
    RIDER_REINSTATED = "rider.reinstated"
    RIDER_ISSUE_CREATED = "rider.issue.created"
    RIDER_ISSUE_STATUS_CHANGED = "rider.issue.status_changed"


class Queues:
    # user-service queues
    USER_SERVICE_USER_REGISTERED = "user-service.user-registered"
    USER_SERVICE_RIDE_EVENTS = "user-service.ride-events"

    # notification-service queues
    NOTIFICATION_AUTH_EVENTS = "notification-service.auth-events"
    NOTIFICATION_RIDE_EVENTS = "notification-service.ride-events"
    NOTIFICATION_PAYMENT_EVENTS = "notification-service.payment-events"
    NOTIFICATION_FLEET_EVENTS = "notification-service.fleet-events"

    # payment-service queues
    PAYMENT_RIDE_COMPLETED = "payment-service.ride-completed"
    PAYMENT_RIDE_CANCELLED = "payment-service.ride-cancelled"

    # ride-service queues
    RIDE_DRIVER_STATUS = "ride-service.driver-status"
    RIDE_TRACKING_UPDATES = "ride-service.tracking-updates"
    RIDE_PAYMENT_EVENTS = "ride-service.payment-events"

    # user-service queues (ride-related)
    USER_SERVICE_RATING_SUBMITTED = "user-service.rating-submitted"

    # tracking-service queues
    TRACKING_RIDE_LIFECYCLE = "tracking-service.ride-lifecycle"

    # location-service queues
    LOCATION_RIDE_EVENTS = "location-service.ride-events"

    # notification-service chat queues
    NOTIFICATION_CHAT_EVENTS = "notification-service.chat-events"

    # Dead letter queue
    DLQ_ALL_FAILED = "dlq.all-failed"
