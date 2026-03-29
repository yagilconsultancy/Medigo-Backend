import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.reaction_repo import ReactionRepository
from app.services.chat_service import ChatService
from app.services.email_service import (
    send_driver_invite_email,
    send_password_reset_email,
)
from app.services.notification_service import NotificationService
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import (
    DriverInviteSentPayload,
    EventEnvelope,
    PasswordResetRequestedPayload,
    PaymentCompletedPayload,
    RideRequestPayload,
    RideStatusChangedPayload,
    UserRegisteredPayload,
)
from mediride_common.schemas.enums import NotificationType

logger = logging.getLogger(__name__)


class AuthEventConsumer(BaseEventConsumer):
    """Consumes auth events to send email notifications."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type == RoutingKeys.USER_REGISTERED:
            payload = UserRegisteredPayload(**envelope.payload)
            if payload.email:
                logger.info(
                    f"User registered notification for {payload.email} "
                    f"(OTP sent by auth-service directly in dev mode)"
                )

        elif envelope.event_type == RoutingKeys.DRIVER_INVITE_SENT:
            payload = DriverInviteSentPayload(**envelope.payload)
            await send_driver_invite_email(
                to=payload.email,
                fleet_name=payload.fleet_name,
                invite_token=payload.invite_token,
            )
            logger.info(f"Driver invite email sent to {payload.email}")

        elif envelope.event_type == RoutingKeys.PASSWORD_RESET_REQUESTED:
            payload = PasswordResetRequestedPayload(**envelope.payload)
            await send_password_reset_email(
                to=payload.email,
                reset_token=payload.reset_token,
            )
            logger.info(f"Password reset email sent to {payload.email}")


class RideEventConsumer(BaseEventConsumer):
    """Consumes ride events to create in-app notification records."""

    def __init__(self, broker: RabbitMQBroker, session_factory: async_sessionmaker[AsyncSession]):
        super().__init__(broker)
        self.session_factory = session_factory

    async def handle(self, envelope: EventEnvelope) -> None:
        async with self.session_factory() as session:
            try:
                svc = NotificationService(NotificationRepository(session))

                if envelope.event_type == RoutingKeys.RIDE_CONFIRMED:
                    payload = RideStatusChangedPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.rider_id,
                        title="Ride Confirmed",
                        body="Your ride has been confirmed and is being processed.",
                        notification_type=NotificationType.RIDE_UPDATE,
                        data={"ride_id": str(payload.ride_id), "screen": "ride_detail"},
                    )

                elif envelope.event_type == RoutingKeys.RIDE_DRIVER_ASSIGNED:
                    payload = RideStatusChangedPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.rider_id,
                        title="Driver Assigned",
                        body="A driver has been assigned to your ride.",
                        notification_type=NotificationType.RIDE_UPDATE,
                        data={
                            "ride_id": str(payload.ride_id),
                            "driver_id": str(payload.driver_id),
                            "screen": "ride_detail",
                        },
                    )

                elif envelope.event_type == RoutingKeys.RIDE_DRIVER_EN_ROUTE:
                    payload = RideStatusChangedPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.rider_id,
                        title="Driver En Route",
                        body="Your driver is on the way to pick you up.",
                        notification_type=NotificationType.RIDE_UPDATE,
                        data={"ride_id": str(payload.ride_id), "screen": "ride_tracking"},
                    )

                elif envelope.event_type == RoutingKeys.RIDE_DRIVER_ARRIVED:
                    payload = RideStatusChangedPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.rider_id,
                        title="Driver Arrived",
                        body="Your driver has arrived at the pickup location.",
                        notification_type=NotificationType.RIDE_UPDATE,
                        data={"ride_id": str(payload.ride_id), "screen": "ride_tracking"},
                    )

                elif envelope.event_type == RoutingKeys.RIDE_COMPLETED:
                    payload = RideStatusChangedPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.rider_id,
                        title="Ride Completed",
                        body="Your ride has been completed. Please rate your experience.",
                        notification_type=NotificationType.RIDE_UPDATE,
                        data={"ride_id": str(payload.ride_id), "screen": "ride_rating"},
                    )
                    if payload.driver_id:
                        await svc.create_notification(
                            user_id=payload.driver_id,
                            title="Ride Completed",
                            body="You have completed the ride.",
                            notification_type=NotificationType.RIDE_UPDATE,
                            data={"ride_id": str(payload.ride_id), "screen": "ride_summary"},
                        )

                elif envelope.event_type == RoutingKeys.RIDE_CANCELLED:
                    payload = RideStatusChangedPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.rider_id,
                        title="Ride Cancelled",
                        body="Your ride has been cancelled.",
                        notification_type=NotificationType.RIDE_UPDATE,
                        data={"ride_id": str(payload.ride_id), "screen": "ride_history"},
                    )
                    if payload.driver_id:
                        await svc.create_notification(
                            user_id=payload.driver_id,
                            title="Ride Cancelled",
                            body="A ride you were assigned to has been cancelled.",
                            notification_type=NotificationType.RIDE_UPDATE,
                            data={"ride_id": str(payload.ride_id), "screen": "ride_history"},
                        )

                elif envelope.event_type == RoutingKeys.RIDE_REQUEST_SENT:
                    payload = RideRequestPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.driver_id,
                        title="New Ride Request",
                        body=f"New ride request from {payload.rider_name}.",
                        notification_type=NotificationType.RIDE_UPDATE,
                        data={"ride_id": str(payload.ride_id), "screen": "ride_request"},
                    )

                await session.commit()
            except Exception:
                await session.rollback()
                raise


class PaymentEventConsumer(BaseEventConsumer):
    """Consumes payment events to create in-app notification records."""

    def __init__(self, broker: RabbitMQBroker, session_factory: async_sessionmaker[AsyncSession]):
        super().__init__(broker)
        self.session_factory = session_factory

    async def handle(self, envelope: EventEnvelope) -> None:
        async with self.session_factory() as session:
            try:
                svc = NotificationService(NotificationRepository(session))

                if envelope.event_type == RoutingKeys.PAYMENT_COMPLETED:
                    payload = PaymentCompletedPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.user_id,
                        title="Payment Processed",
                        body=f"Payment of ${payload.amount:.2f} has been processed.",
                        notification_type=NotificationType.PAYMENT,
                        data={
                            "ride_id": str(payload.ride_id),
                            "transaction_id": str(payload.transaction_id),
                            "screen": "payment_receipt",
                        },
                    )

                elif envelope.event_type == RoutingKeys.PAYMENT_FAILED:
                    payload = PaymentCompletedPayload(**envelope.payload)
                    await svc.create_notification(
                        user_id=payload.user_id,
                        title="Payment Failed",
                        body="Your payment could not be processed. Please update your payment method.",
                        notification_type=NotificationType.PAYMENT,
                        data={
                            "ride_id": str(payload.ride_id),
                            "screen": "payment_methods",
                        },
                    )

                await session.commit()
            except Exception:
                await session.rollback()
                raise


class ChatConversationConsumer(BaseEventConsumer):
    """Auto-creates a chat conversation when a driver is assigned to a ride."""

    def __init__(self, broker: RabbitMQBroker, session_factory: async_sessionmaker[AsyncSession]):
        super().__init__(broker)
        self.session_factory = session_factory

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type != RoutingKeys.RIDE_DRIVER_ASSIGNED:
            return

        payload = RideStatusChangedPayload(**envelope.payload)
        if not payload.driver_id:
            logger.warning(f"Driver assigned event missing driver_id for ride {payload.ride_id}")
            return

        async with self.session_factory() as session:
            try:
                chat_svc = ChatService(
                    conv_repo=ConversationRepository(session),
                    msg_repo=MessageRepository(session),
                    reaction_repo=ReactionRepository(session),
                )
                conv = await chat_svc.get_or_create_conversation(
                    ride_id=payload.ride_id,
                    driver_id=payload.driver_id,
                    rider_id=payload.rider_id,
                )
                await session.commit()
                logger.info(
                    f"Chat conversation {conv.id} created for ride {payload.ride_id} "
                    f"(rider={payload.rider_id}, driver={payload.driver_id})"
                )
            except Exception:
                await session.rollback()
                raise


async def setup_consumers(broker: RabbitMQBroker) -> None:
    """Set up all event consumers for the notification service."""
    from app.dependencies import get_session_factory

    session_factory = get_session_factory()

    auth_consumer = AuthEventConsumer(broker)
    await auth_consumer.setup_queue(
        queue_name=Queues.NOTIFICATION_AUTH_EVENTS,
        exchange_name=Exchanges.AUTH,
        routing_keys=[
            RoutingKeys.USER_REGISTERED,
            RoutingKeys.USER_VERIFIED,
            RoutingKeys.DRIVER_INVITE_SENT,
            RoutingKeys.PASSWORD_RESET_REQUESTED,
        ],
    )

    ride_consumer = RideEventConsumer(broker, session_factory)
    await ride_consumer.setup_queue(
        queue_name=Queues.NOTIFICATION_RIDE_EVENTS,
        exchange_name=Exchanges.RIDES,
        routing_keys=[
            RoutingKeys.RIDE_CONFIRMED,
            RoutingKeys.RIDE_DRIVER_ASSIGNED,
            RoutingKeys.RIDE_DRIVER_EN_ROUTE,
            RoutingKeys.RIDE_DRIVER_ARRIVED,
            RoutingKeys.RIDE_COMPLETED,
            RoutingKeys.RIDE_CANCELLED,
            RoutingKeys.RIDE_REQUEST_SENT,
        ],
    )

    payment_consumer = PaymentEventConsumer(broker, session_factory)
    await payment_consumer.setup_queue(
        queue_name=Queues.NOTIFICATION_PAYMENT_EVENTS,
        exchange_name=Exchanges.PAYMENTS,
        routing_keys=[
            RoutingKeys.PAYMENT_COMPLETED,
            RoutingKeys.PAYMENT_FAILED,
        ],
    )

    chat_consumer = ChatConversationConsumer(broker, session_factory)
    await chat_consumer.setup_queue(
        queue_name=Queues.NOTIFICATION_CHAT_EVENTS,
        exchange_name=Exchanges.RIDES,
        routing_keys=[
            RoutingKeys.RIDE_DRIVER_ASSIGNED,
        ],
    )

    logger.info("Notification service consumers initialized")
