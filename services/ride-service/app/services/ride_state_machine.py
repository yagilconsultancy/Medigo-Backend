from mediride_common.events.constants import RoutingKeys
from mediride_common.exceptions import ValidationError
from mediride_common.schemas.enums import RideStatus

VALID_TRANSITIONS: dict[str, list[str]] = {
    RideStatus.REQUESTED: [RideStatus.CONFIRMED, RideStatus.CANCELLED],
    RideStatus.CONFIRMED: [RideStatus.DRIVER_ASSIGNED, RideStatus.CANCELLED],
    RideStatus.DRIVER_ASSIGNED: [RideStatus.DRIVER_EN_ROUTE, RideStatus.CANCELLED],
    RideStatus.DRIVER_EN_ROUTE: [RideStatus.DRIVER_ARRIVED, RideStatus.CANCELLED],
    RideStatus.DRIVER_ARRIVED: [RideStatus.IN_PROGRESS, RideStatus.NO_SHOW, RideStatus.CANCELLED],
    RideStatus.IN_PROGRESS: [RideStatus.COMPLETED, RideStatus.CANCELLED],
    RideStatus.COMPLETED: [],
    RideStatus.CANCELLED: [],
    RideStatus.NO_SHOW: [],
}

STATUS_ROUTING_KEYS: dict[str, str] = {
    RideStatus.CONFIRMED: RoutingKeys.RIDE_CONFIRMED,
    RideStatus.DRIVER_ASSIGNED: RoutingKeys.RIDE_DRIVER_ASSIGNED,
    RideStatus.DRIVER_EN_ROUTE: RoutingKeys.RIDE_DRIVER_EN_ROUTE,
    RideStatus.DRIVER_ARRIVED: RoutingKeys.RIDE_DRIVER_ARRIVED,
    RideStatus.IN_PROGRESS: RoutingKeys.RIDE_IN_PROGRESS,
    RideStatus.COMPLETED: RoutingKeys.RIDE_COMPLETED,
    RideStatus.CANCELLED: RoutingKeys.RIDE_CANCELLED,
    RideStatus.NO_SHOW: RoutingKeys.RIDE_NO_SHOW,
}


def validate_transition(from_status: str, to_status: str) -> bool:
    allowed = VALID_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise ValidationError(
            f"Cannot transition from '{from_status}' to '{to_status}'. "
            f"Allowed transitions: {allowed}"
        )
    return True


def get_routing_key_for_status(status: str) -> str:
    return STATUS_ROUTING_KEYS.get(status, "")
