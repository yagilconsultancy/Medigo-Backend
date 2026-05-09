import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.reaction_repo import ReactionRepository
from app.services.chat_service import ChatService
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.services.email_service import (
    send_admin_invite_email,
    send_driver_invite_email,
    send_otp_email,
    send_password_reset_email,
    send_ride_notification_email,
)
from app.services.notification_service import NotificationService
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import (
    AdminInviteSentPayload,
    DriverInviteSentPayload,
    EventEnvelope,
    PasswordResetRequestedPayload,
    PaymentCompletedPayload,
    RideCreatedPayload,
    RideRequestPayload,
    RideStatusChangedPayload,
    UserOTPRequestedPayload,
    UserRegisteredPayload,
)
from mediride_common.schemas.enums import NotificationType, RideStatus

logger = logging.getLogger(__name__)


class AuthEventConsumer(BaseEventConsumer):
    """Consumes auth events to send email notifications."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type == RoutingKeys.USER_REGISTERED:
            payload = UserRegisteredPayload(**envelope.payload)
            if payload.email:
                logger.info(f"User registered event received for {payload.email}")

        elif envelope.event_type == RoutingKeys.USER_OTP_REQUESTED:
            payload = UserOTPRequestedPayload(**envelope.payload)
            if payload.email and payload.channel == "email":
                sent = await send_otp_email(
                    to=payload.email,
                    otp_code=payload.otp_code,
                )
                if sent:
                    logger.info(
                        "OTP email sent to %s for purpose %s",
                        payload.email,
                        payload.purpose,
                    )
                else:
                    logger.error(
                        "OTP email failed for %s for purpose %s",
                        payload.email,
                        payload.purpose,
                    )
            else:
                logger.info(
                    "OTP requested for user %s via unsupported channel %s",
                    payload.user_id,
                    payload.channel,
                )

        elif envelope.event_type == RoutingKeys.DRIVER_INVITE_SENT:
            payload = DriverInviteSentPayload(**envelope.payload)
            sent = await send_driver_invite_email(
                to=payload.email,
                fleet_name=payload.fleet_name,
                invite_token=payload.invite_token,
                temporary_password=payload.temporary_password,
            )
            if sent:
                logger.info("Driver invite email sent to %s", payload.email)
            else:
                logger.error("Driver invite email failed for %s", payload.email)

        elif envelope.event_type == RoutingKeys.ADMIN_INVITE_SENT:
            payload = AdminInviteSentPayload(**envelope.payload)
            sent = await send_admin_invite_email(
                to=payload.email,
                full_name=payload.full_name,
                role_display_name=payload.role_display_name,
                invite_token=payload.invite_token,
                invited_by_name=payload.invited_by_name,
            )
            if sent:
                logger.info("Admin invite email sent to %s", payload.email)
            else:
                logger.error("Admin invite email failed for %s", payload.email)

        elif envelope.event_type == RoutingKeys.PASSWORD_RESET_REQUESTED:
            payload = PasswordResetRequestedPayload(**envelope.payload)
            sent = await send_password_reset_email(
                to=payload.email,
                reset_token=payload.reset_token,
            )
            if sent:
                logger.info("Password reset email sent to %s", payload.email)
            else:
                logger.error("Password reset email failed for %s", payload.email)


class RideEventConsumer(BaseEventConsumer):
    """Consumes ride events to send push notifications and emails."""

    def __init__(self, broker: RabbitMQBroker, session_factory: async_sessionmaker[AsyncSession]):
        super().__init__(broker)
        self.session_factory = session_factory
        self.user_client = UserServiceClient(settings.USER_SERVICE_URL)
        self._status_by_event = {
            RoutingKeys.RIDE_CONFIRMED: RideStatus.CONFIRMED,
            RoutingKeys.RIDE_DRIVER_ASSIGNED: RideStatus.DRIVER_ASSIGNED,
            RoutingKeys.RIDE_DRIVER_EN_ROUTE: RideStatus.DRIVER_EN_ROUTE,
            RoutingKeys.RIDE_DRIVER_ARRIVED: RideStatus.DRIVER_ARRIVED,
            RoutingKeys.RIDE_IN_PROGRESS: RideStatus.IN_PROGRESS,
            RoutingKeys.RIDE_COMPLETED: RideStatus.COMPLETED,
            RoutingKeys.RIDE_CANCELLED: RideStatus.CANCELLED,
            RoutingKeys.RIDE_NO_SHOW: RideStatus.NO_SHOW,
        }

    def _parse_status_payload(
        self, envelope: EventEnvelope,
    ) -> RideStatusChangedPayload | None:
        payload_data = dict(envelope.payload or {})
        payload_data.setdefault("to_status", self._status_by_event.get(envelope.event_type))

        if not payload_data.get("ride_id") or not payload_data.get("rider_id"):
            logger.warning(
                "Skipping ride status notification: missing ride_id or rider_id",
                extra={
                    "event_type": envelope.event_type,
                    "payload_keys": sorted(payload_data.keys()),
                },
            )
            return None

        return RideStatusChangedPayload(**payload_data)

    async def _send_notification(
        self,
        svc: NotificationService,
        user_id: UUID,
        title: str,
        body: str,
        data: dict,
        ride_details: dict | None = None,
    ) -> None:
        """Send both push notification and email."""
        # Create in-app push notification
        await svc.create_notification(
            user_id=user_id,
            title=title,
            body=body,
            notification_type=NotificationType.RIDE_UPDATE,
            data=data,
        )

        # Send email notification
        user_info = await self.user_client.get_user_email(user_id)
        if user_info and user_info.get("email"):
            await send_ride_notification_email(
                to=user_info["email"],
                name=user_info["name"],
                subject=f"MediRide - {title}",
                title=title,
                body=body,
                ride_details=ride_details,
            )

    async def handle(self, envelope: EventEnvelope) -> None:
        async with self.session_factory() as session:
            try:
                svc = NotificationService(NotificationRepository(session))

                # RIDE CREATED - Rider books a new ride
                if envelope.event_type == RoutingKeys.RIDE_CREATED:
                    payload = RideCreatedPayload(**envelope.payload)
                    ride_details = {
                        "ride_id": str(payload.ride_id),
                        "pickup_address": payload.pickup_address,
                        "destination_address": payload.destination_address,
                        "scheduled_at": str(payload.scheduled_at),
                    }
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Ride Request Received",
                        body="Your ride request has been received and is awaiting approval.",
                        data={"ride_id": str(payload.ride_id), "screen": "ride_detail"},
                        ride_details=ride_details,
                    )

                # RIDE CONFIRMED - Admin approves the ride
                elif envelope.event_type == RoutingKeys.RIDE_CONFIRMED:
                    payload = self._parse_status_payload(envelope)
                    if not payload:
                        return
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Ride Confirmed",
                        body="Your ride has been confirmed and is being processed.",
                        data={"ride_id": str(payload.ride_id), "screen": "ride_detail"},
                    )

                # DRIVER ASSIGNED - Driver is assigned to the ride
                elif envelope.event_type == RoutingKeys.RIDE_DRIVER_ASSIGNED:
                    payload = self._parse_status_payload(envelope)
                    if not payload:
                        return
                    driver_name = None
                    if payload.driver_id:
                        driver_profile = await self.user_client.get_driver_profile(
                            payload.driver_id
                        )
                        if driver_profile:
                            driver_name = (
                                f"{driver_profile.get('first_name', '')} "
                                f"{driver_profile.get('last_name', '')}"
                            ).strip() or None
                    # Notify rider
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Driver Assigned",
                        body=(
                            f"{driver_name} has been assigned to your ride."
                            if driver_name else
                            "A driver has been assigned to your ride."
                        ),
                        data={
                            "ride_id": str(payload.ride_id),
                            "driver_id": str(payload.driver_id) if payload.driver_id else None,
                            "driver_name": driver_name,
                            "status": str(RideStatus.DRIVER_ASSIGNED),
                            "status_label": "Driver Assigned",
                            "screen": "ride_detail",
                        },
                    )
                    # Notify driver
                    if payload.driver_id:
                        await self._send_notification(
                            svc=svc,
                            user_id=payload.driver_id,
                            title="New Ride Assignment",
                            body="You have been assigned to a new ride.",
                            data={"ride_id": str(payload.ride_id), "screen": "ride_detail"},
                        )

                # DRIVER EN ROUTE - Driver is on the way
                elif envelope.event_type == RoutingKeys.RIDE_DRIVER_EN_ROUTE:
                    payload = self._parse_status_payload(envelope)
                    if not payload:
                        return
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Driver En Route",
                        body="Your driver is on the way to pick you up.",
                        data={"ride_id": str(payload.ride_id), "screen": "ride_tracking"},
                    )

                # DRIVER ARRIVED - Driver has arrived at pickup
                elif envelope.event_type == RoutingKeys.RIDE_DRIVER_ARRIVED:
                    payload = self._parse_status_payload(envelope)
                    if not payload:
                        return
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Driver Arrived",
                        body="Your driver has arrived at the pickup location.",
                        data={"ride_id": str(payload.ride_id), "screen": "ride_tracking"},
                    )

                # RIDE IN PROGRESS - Ride has started
                elif envelope.event_type == RoutingKeys.RIDE_IN_PROGRESS:
                    payload = self._parse_status_payload(envelope)
                    if not payload:
                        return
                    # Notify rider
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Ride Started",
                        body="Your ride is now in progress.",
                        data={"ride_id": str(payload.ride_id), "screen": "ride_tracking"},
                    )
                    # Notify driver
                    if payload.driver_id:
                        await self._send_notification(
                            svc=svc,
                            user_id=payload.driver_id,
                            title="Ride Started",
                            body="The ride is now in progress.",
                            data={"ride_id": str(payload.ride_id), "screen": "ride_tracking"},
                        )

                # RIDE COMPLETED - Ride has finished successfully
                elif envelope.event_type == RoutingKeys.RIDE_COMPLETED:
                    payload = self._parse_status_payload(envelope)
                    if not payload:
                        return
                    # Notify rider
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Ride Completed",
                        body="Your ride has been completed. Please rate your experience.",
                        data={"ride_id": str(payload.ride_id), "screen": "ride_rating"},
                    )
                    # Notify driver
                    if payload.driver_id:
                        await self._send_notification(
                            svc=svc,
                            user_id=payload.driver_id,
                            title="Ride Completed",
                            body="You have successfully completed the ride.",
                            data={"ride_id": str(payload.ride_id), "screen": "ride_summary"},
                        )

                # RIDE CANCELLED - Ride was cancelled
                elif envelope.event_type == RoutingKeys.RIDE_CANCELLED:
                    payload = self._parse_status_payload(envelope)
                    if not payload:
                        return
                    # Notify rider
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Ride Cancelled",
                        body="Your ride has been cancelled.",
                        data={"ride_id": str(payload.ride_id), "screen": "ride_history"},
                    )
                    # Notify driver if assigned
                    if payload.driver_id:
                        await self._send_notification(
                            svc=svc,
                            user_id=payload.driver_id,
                            title="Ride Cancelled",
                            body="A ride you were assigned to has been cancelled.",
                            data={"ride_id": str(payload.ride_id), "screen": "ride_history"},
                        )

                # NO SHOW - Rider didn't show up
                elif envelope.event_type == RoutingKeys.RIDE_NO_SHOW:
                    payload = self._parse_status_payload(envelope)
                    if not payload:
                        return
                    # Notify rider
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.rider_id,
                        title="Ride Marked as No-Show",
                        body="Your ride was marked as a no-show. Please contact support if this is incorrect.",
                        data={"ride_id": str(payload.ride_id), "screen": "support"},
                    )
                    # Notify driver
                    if payload.driver_id:
                        await self._send_notification(
                            svc=svc,
                            user_id=payload.driver_id,
                            title="Ride Marked as No-Show",
                            body="The ride has been marked as a no-show.",
                            data={"ride_id": str(payload.ride_id), "screen": "ride_summary"},
                        )

                # RIDE REQUEST (legacy - for direct driver requests)
                elif envelope.event_type == RoutingKeys.RIDE_REQUEST_SENT:
                    payload = RideRequestPayload(**envelope.payload)
                    await self._send_notification(
                        svc=svc,
                        user_id=payload.driver_id,
                        title="New Ride Request",
                        body=f"New ride request from {payload.rider_name}.",
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
            RoutingKeys.USER_OTP_REQUESTED,
            RoutingKeys.DRIVER_INVITE_SENT,
            RoutingKeys.ADMIN_INVITE_SENT,
            RoutingKeys.PASSWORD_RESET_REQUESTED,
        ],
    )

    ride_consumer = RideEventConsumer(broker, session_factory)
    await ride_consumer.setup_queue(
        queue_name=Queues.NOTIFICATION_RIDE_EVENTS,
        exchange_name=Exchanges.RIDES,
        routing_keys=[
            RoutingKeys.RIDE_CREATED,  # When rider books a ride
            RoutingKeys.RIDE_CONFIRMED,  # When admin approves
            RoutingKeys.RIDE_DRIVER_ASSIGNED,  # When driver is assigned
            RoutingKeys.RIDE_DRIVER_EN_ROUTE,  # Driver on the way
            RoutingKeys.RIDE_DRIVER_ARRIVED,  # Driver arrived at pickup
            RoutingKeys.RIDE_IN_PROGRESS,  # Ride started
            RoutingKeys.RIDE_COMPLETED,  # Ride finished
            RoutingKeys.RIDE_CANCELLED,  # Ride cancelled
            RoutingKeys.RIDE_NO_SHOW,  # Rider no-show
            RoutingKeys.RIDE_REQUEST_SENT,  # Legacy direct request
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
