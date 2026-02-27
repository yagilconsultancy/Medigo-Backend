import logging

from app.services.email_service import send_driver_invite_email, send_otp_email
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import (
    DriverInviteSentPayload,
    EventEnvelope,
    UserRegisteredPayload,
)

logger = logging.getLogger(__name__)


class AuthEventConsumer(BaseEventConsumer):
    """Consumes auth events to send notifications."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type == RoutingKeys.USER_REGISTERED:
            payload = UserRegisteredPayload(**envelope.payload)
            if payload.email:
                # In a real system, the OTP would be included in the event
                # or we'd generate a notification with a link
                logger.info(
                    f"User registered notification for {payload.email} "
                    f"(OTP sent by auth-service directly in dev mode)"
                )

        elif envelope.event_type == RoutingKeys.DRIVER_INVITE_SENT:
            payload = DriverInviteSentPayload(**envelope.payload)
            await send_driver_invite_email(
                to=payload.email,
                business_name=payload.business_name,
                invite_token=payload.invite_token,
            )
            logger.info(f"Driver invite email sent to {payload.email}")


async def setup_consumers(broker: RabbitMQBroker) -> None:
    """Set up all event consumers for the notification service."""
    auth_consumer = AuthEventConsumer(broker)
    await auth_consumer.setup_queue(
        queue_name=Queues.NOTIFICATION_AUTH_EVENTS,
        exchange_name=Exchanges.AUTH,
        routing_keys=[
            RoutingKeys.USER_REGISTERED,
            RoutingKeys.USER_VERIFIED,
            RoutingKeys.DRIVER_INVITE_SENT,
        ],
    )
    logger.info("Notification service consumers initialized")
