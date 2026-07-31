import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.conversation_repo import ConversationRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.reaction_repo import ReactionRepository
from app.clients.payment_service_client import PaymentServiceClient
from app.services.chat_service import ChatService
from app.clients.user_service_client import UserServiceClient
from app.config import settings
from app.services.email_service import (
    send_account_reactivation_email,
    send_admin_invite_email,
    send_admin_ride_booking_email,
    send_driver_invite_email,
    send_fleet_application_approved_email,
    send_fleet_application_received_email,
    send_fleet_application_rejected_email,
    send_fleet_info_request_email,
    send_otp_email,
    send_password_reset_email,
    send_payment_receipt_email,
    send_ride_notification_email,
)
from app.services.notification_service import NotificationService
from mediride_common.events.broker import RabbitMQBroker
from mediride_common.events.constants import Exchanges, Queues, RoutingKeys
from mediride_common.events.consumer import BaseEventConsumer
from mediride_common.events.schemas import (
    AdminInviteSentPayload,
    DriverEmailChangedPayload,
    DriverInviteSentPayload,
    FleetApplicationApprovedPayload,
    EventEnvelope,
    FleetApplicationCreatedPayload,
    FleetApplicationInfoRequestedPayload,
    FleetApplicationRejectedPayload,
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

        elif envelope.event_type == RoutingKeys.DRIVER_EMAIL_CHANGED:
            payload = DriverEmailChangedPayload(**envelope.payload)
            sent = await send_account_reactivation_email(
                to=payload.email,
                name=payload.name,
                reactivation_link=payload.reactivation_link,
            )
            if sent:
                logger.info("Reactivation email sent to %s", payload.email)
            else:
                logger.error("Reactivation email failed for %s", payload.email)

        elif envelope.event_type == RoutingKeys.ADMIN_INVITE_SENT:
            payload = AdminInviteSentPayload(**envelope.payload)
            sent = await send_admin_invite_email(
                to=payload.email,
                full_name=payload.full_name,
                role_display_name=payload.role_display_name,
                temporary_password=payload.temporary_password,
                invited_by_name=payload.invited_by_name,
            )
            if sent:
                logger.info("Admin credentials email sent to %s", payload.email)
            else:
                logger.error("Admin credentials email failed for %s", payload.email)

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
                subject=f"MediGo - {title}",
                title=title,
                body=body,
                ride_details=ride_details,
            )

    async def _send_admin_booking_alert(self, payload: RideCreatedPayload) -> None:
        """Email the ops team about a new booking.

        Never raises: a failed admin alert must not requeue the event and
        re-send the rider's confirmation.
        """
        recipients = settings.admin_booking_alert_recipients
        if not recipients:
            return

        # A recurring booking creates one ride per occurrence. Alert on the
        # booking itself only, or a long series would flood the inbox.
        if payload.is_recurring_occurrence:
            logger.debug(
                "Skipping admin booking alert for generated occurrence of ride %s",
                payload.ride_id,
            )
            return

        try:
            booking = payload.model_dump()
            rider_info = await self.user_client.get_user_email(payload.rider_id)
            if rider_info:
                booking["booked_by_name"] = rider_info.get("name")
                booking["booked_by_email"] = rider_info.get("email")

            await send_admin_ride_booking_email(to=recipients, booking=booking)
            logger.info(
                "Admin booking alert sent to %s for ride %s",
                ", ".join(recipients),
                payload.ride_id,
            )
        except Exception:
            logger.exception(
                "Admin booking alert failed for ride %s", payload.ride_id
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
                    # Notify the ops team so the booking gets reviewed
                    await self._send_admin_booking_alert(payload)

                # RIDE UPDATED - Admin edits the booking details
                elif envelope.event_type == RoutingKeys.RIDE_UPDATED:
                    data = dict(envelope.payload or {})
                    rider_id = data.get("rider_id")
                    ride_id = data.get("ride_id")
                    if not rider_id or not ride_id:
                        logger.warning(
                            "Skipping ride updated notification: missing ride_id or rider_id",
                            extra={"payload_keys": sorted(data.keys())},
                        )
                        return
                    await self._send_notification(
                        svc=svc,
                        user_id=UUID(str(rider_id)),
                        title="Booking Updated",
                        body="Your booking details have been updated by our team.",
                        data={"ride_id": str(ride_id), "screen": "ride_detail"},
                    )
                    # The assigned driver is working off these details, so they
                    # need to know they changed too.
                    driver_id = data.get("driver_id")
                    if driver_id:
                        changed = data.get("changed_fields") or []
                        await self._send_notification(
                            svc=svc,
                            user_id=UUID(str(driver_id)),
                            title="Ride Details Updated",
                            body=(
                                "A ride assigned to you has been updated. "
                                "Check the latest details before pickup."
                            ),
                            data={
                                "ride_id": str(ride_id),
                                "changed_fields": changed,
                                "screen": "ride_detail",
                            },
                        )

                # RIDE NOTE ADDED - Admin left a note for the assigned driver
                elif envelope.event_type == RoutingKeys.RIDE_NOTE_ADDED:
                    data = dict(envelope.payload or {})
                    ride_id = data.get("ride_id")
                    driver_id = data.get("driver_id")
                    if not ride_id or not driver_id:
                        logger.warning(
                            "Skipping ride note notification: missing ride_id or driver_id",
                            extra={"payload_keys": sorted(data.keys())},
                        )
                        return
                    await self._send_notification(
                        svc=svc,
                        user_id=UUID(str(driver_id)),
                        title="New Note From Dispatch",
                        body="Dispatch added a note to one of your rides.",
                        data={
                            "ride_id": str(ride_id),
                            "note_id": str(data.get("note_id") or ""),
                            "screen": "ride_detail",
                        },
                    )

                # DRIVER UNASSIGNED - Ride was taken off this driver
                elif envelope.event_type == RoutingKeys.RIDE_DRIVER_UNASSIGNED:
                    data = dict(envelope.payload or {})
                    ride_id = data.get("ride_id")
                    driver_id = data.get("driver_id")
                    if not ride_id or not driver_id:
                        logger.warning(
                            "Skipping driver unassigned notification: missing ride_id or driver_id",
                            extra={"payload_keys": sorted(data.keys())},
                        )
                        return
                    await self._send_notification(
                        svc=svc,
                        user_id=UUID(str(driver_id)),
                        title="Ride Reassigned",
                        body="A ride previously assigned to you has been reassigned.",
                        data={"ride_id": str(ride_id), "screen": "ride_history"},
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
        self.user_client = UserServiceClient(settings.USER_SERVICE_URL)
        self.payment_client = PaymentServiceClient(settings.PAYMENT_SERVICE_URL)

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
                    user_settings = await self.user_client.get_user_settings(payload.user_id)
                    if user_settings and user_settings.get("email_ride_receipts") is False:
                        logger.info(
                            "Skipping receipt email for user %s because email_ride_receipts is disabled",
                            payload.user_id,
                        )
                    else:
                        user_info = await self.user_client.get_user_email(payload.user_id)
                        if user_info and user_info.get("email"):
                            receipt = await self.payment_client.get_receipt(
                                payload.ride_id,
                                payload.user_id,
                            )
                            receipt_data = receipt or {
                                "trip_number": f"TRIP-{str(payload.ride_id)[:6].upper()}",
                                "currency": "CAD",
                                "total_fare": payload.amount,
                                "ride_date": None,
                                "pickup_address": "",
                                "destination_address": "",
                                "payment_method_type": "Card",
                                "payment_method_last_four": "",
                                "paid_at": None,
                            }
                            await send_payment_receipt_email(
                                to=user_info["email"],
                                name=user_info["name"],
                                receipt=receipt_data,
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


class FleetEventConsumer(BaseEventConsumer):
    """Consumes fleet events to send email notifications to applicants."""

    async def handle(self, envelope: EventEnvelope) -> None:
        if envelope.event_type == RoutingKeys.FLEET_APPLICATION_CREATED:
            payload = FleetApplicationCreatedPayload(**envelope.payload)
            if payload.created_by != "public":
                logger.info(
                    "Skipping fleet application confirmation email for non-public application %s",
                    payload.application_id,
                )
                return

            sent = await send_fleet_application_received_email(
                to=payload.email,
                company_name=payload.company_name,
            )
            if sent:
                logger.info(
                    "Fleet application confirmation email sent to %s for application %s",
                    payload.email,
                    payload.application_id,
                )
            else:
                logger.error(
                    "Fleet application confirmation email failed for %s",
                    payload.email,
                )

        elif envelope.event_type == RoutingKeys.FLEET_APPLICATION_INFO_REQUESTED:
            payload = FleetApplicationInfoRequestedPayload(**envelope.payload)
            sent = await send_fleet_info_request_email(
                to=payload.email,
                company_name=payload.company_name,
                message=payload.message,
            )
            if sent:
                logger.info(
                    "Fleet info request email sent to %s for application %s",
                    payload.email,
                    payload.application_id,
                )
            else:
                logger.error(
                    "Fleet info request email failed for %s",
                    payload.email,
                )

        elif envelope.event_type == RoutingKeys.FLEET_APPLICATION_APPROVED:
            payload = FleetApplicationApprovedPayload(**envelope.payload)
            sent = await send_fleet_application_approved_email(
                to=payload.email,
                company_name=payload.company_name,
            )
            if sent:
                logger.info(
                    "Fleet application approved email sent to %s for application %s",
                    payload.email,
                    payload.application_id,
                )
            else:
                logger.error(
                    "Fleet application approved email failed for %s",
                    payload.email,
                )

        elif envelope.event_type == RoutingKeys.FLEET_APPLICATION_REJECTED:
            payload = FleetApplicationRejectedPayload(**envelope.payload)
            sent = await send_fleet_application_rejected_email(
                to=payload.email,
                company_name=payload.company_name,
                reason=payload.reason,
            )
            if sent:
                logger.info(
                    "Fleet application rejected email sent to %s for application %s",
                    payload.email,
                    payload.application_id,
                )
            else:
                logger.error(
                    "Fleet application rejected email failed for %s",
                    payload.email,
                )


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
            RoutingKeys.DRIVER_EMAIL_CHANGED,
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
            RoutingKeys.RIDE_UPDATED,  # When admin edits booking details
            RoutingKeys.RIDE_NOTE_ADDED,  # Admin note flagged for the driver
            RoutingKeys.RIDE_CONFIRMED,  # When admin approves
            RoutingKeys.RIDE_DRIVER_ASSIGNED,  # When driver is assigned
            RoutingKeys.RIDE_DRIVER_UNASSIGNED,  # Ride taken off a driver
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

    fleet_consumer = FleetEventConsumer(broker)
    await fleet_consumer.setup_queue(
        queue_name=Queues.NOTIFICATION_FLEET_EVENTS,
        exchange_name=Exchanges.USERS,
        routing_keys=[
            RoutingKeys.FLEET_APPLICATION_CREATED,
            RoutingKeys.FLEET_APPLICATION_APPROVED,
            RoutingKeys.FLEET_APPLICATION_REJECTED,
            RoutingKeys.FLEET_APPLICATION_INFO_REQUESTED,
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
