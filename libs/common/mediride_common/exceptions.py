class MediRideError(Exception):
    """Base exception for all MediRide errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(self, message: str | None = None, details: dict | None = None):
        self.message = message or self.__class__.message
        self.details = details
        super().__init__(self.message)


class NotFoundError(MediRideError):
    status_code = 404
    error_code = "NOT_FOUND"
    message = "Resource not found"


class ValidationError(MediRideError):
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "Validation failed"


class AuthenticationError(MediRideError):
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"
    message = "Authentication failed"


class AuthorizationError(MediRideError):
    status_code = 403
    error_code = "AUTHORIZATION_ERROR"
    message = "Insufficient permissions"


class ConflictError(MediRideError):
    status_code = 409
    error_code = "CONFLICT"
    message = "Resource already exists"


class RateLimitError(MediRideError):
    status_code = 429
    error_code = "RATE_LIMITED"
    message = "Too many requests"


class ServiceUnavailableError(MediRideError):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
    message = "Service temporarily unavailable"


class RetryableError(MediRideError):
    """Error that can be retried (used in event consumers)."""

    status_code = 500
    error_code = "RETRYABLE_ERROR"
    message = "Temporary error, will retry"
