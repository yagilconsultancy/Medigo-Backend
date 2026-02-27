class Exchanges:
    AUTH = "mediride.auth"
    USERS = "mediride.users"
    RIDES = "mediride.rides"
    PAYMENTS = "mediride.payments"
    TRACKING = "mediride.tracking"
    DLX = "mediride.dlx"


class RoutingKeys:
    # Auth events
    USER_REGISTERED = "user.registered"
    USER_VERIFIED = "user.verified"
    USER_LOGIN = "user.login"
    USER_PASSWORD_CHANGED = "user.password_changed"
    DRIVER_INVITE_SENT = "driver.invite.sent"

    # User events
    PROFILE_CREATED = "profile.created"
    PROFILE_UPDATED = "profile.updated"
    DRIVER_APPROVED = "driver.approved"
    DRIVER_SUSPENDED = "driver.suspended"
    DRIVER_ONLINE = "driver.online"
    DRIVER_OFFLINE = "driver.offline"
    BUSINESS_CREATED = "business.created"
    BUSINESS_UPDATED = "business.updated"

    # Ride events
    RIDE_CREATED = "ride.created"
    RIDE_CONFIRMED = "ride.confirmed"
    RIDE_DRIVER_ASSIGNED = "ride.driver_assigned"
    RIDE_DRIVER_EN_ROUTE = "ride.driver_en_route"
    RIDE_DRIVER_ARRIVED = "ride.driver_arrived"
    RIDE_IN_PROGRESS = "ride.in_progress"
    RIDE_COMPLETED = "ride.completed"
    RIDE_CANCELLED = "ride.cancelled"
    RIDE_NO_SHOW = "ride.no_show"
    RIDE_REQUEST_SENT = "ride.request.sent"
    RIDE_REQUEST_ACCEPTED = "ride.request.accepted"
    RIDE_REQUEST_DECLINED = "ride.request.declined"

    # Payment events
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    EARNINGS_CALCULATED = "earnings.calculated"

    # Tracking events
    DRIVER_LOCATION_UPDATED = "driver.location.updated"
    RIDE_ETA_UPDATED = "ride.eta.updated"


class Queues:
    # user-service queues
    USER_SERVICE_USER_REGISTERED = "user-service.user-registered"

    # notification-service queues
    NOTIFICATION_AUTH_EVENTS = "notification-service.auth-events"
    NOTIFICATION_RIDE_EVENTS = "notification-service.ride-events"
    NOTIFICATION_PAYMENT_EVENTS = "notification-service.payment-events"

    # payment-service queues
    PAYMENT_RIDE_COMPLETED = "payment-service.ride-completed"
    PAYMENT_RIDE_CANCELLED = "payment-service.ride-cancelled"

    # ride-service queues
    RIDE_DRIVER_STATUS = "ride-service.driver-status"
    RIDE_TRACKING_UPDATES = "ride-service.tracking-updates"

    # tracking-service queues
    TRACKING_RIDE_LIFECYCLE = "tracking-service.ride-lifecycle"

    # Dead letter queue
    DLQ_ALL_FAILED = "dlq.all-failed"
