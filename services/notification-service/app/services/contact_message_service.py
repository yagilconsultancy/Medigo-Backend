import html
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact_message import ContactMessage
from app.repositories.contact_message_repo import ContactMessageRepository
from app.config import settings
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

# Map of service types to display labels
SERVICE_TYPE_LABELS = {
    "transportation": "Transportation",
    "partnership": "Partnership Inquiry",
    "platform": "Platform Access",
    "other": "Other",
}


class ContactMessageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ContactMessageRepository(session)

    async def submit_message(
        self,
        full_name: str,
        email: str,
        phone: str | None,
        service_type: str,
        message: str,
    ) -> ContactMessage:
        contact_msg = ContactMessage(
            full_name=full_name,
            email=email,
            phone=phone,
            service_type=service_type,
            message=message,
        )
        contact_msg = await self.repo.create(contact_msg)

        # Email the operations team. Visitor text is escaped so it cannot
        # inject HTML into the email. A failure is logged only: the message
        # is already saved and the visitor still gets a success reply.
        recipients = settings.admin_booking_alert_recipients
        if not recipients:
            logger.warning("No admin recipients set; contact message %s saved without email", contact_msg.id)
            return contact_msg
        try:
            service_label = SERVICE_TYPE_LABELS.get(service_type, service_type)
            safe = {
                "name": html.escape(full_name),
                "email": html.escape(email),
                "phone": html.escape(phone) if phone else "Not provided",
                "service": html.escape(service_label),
                "message": html.escape(message).replace("\n", "<br>"),
            }
            admin_html = f"""
            <html>
            <body>
                <h2>New Contact Form Submission</h2>
                <table style="border-collapse: collapse; width: 100%;">
                    <tr><td style="padding: 8px; font-weight: bold;">Name:</td><td style="padding: 8px;">{safe["name"]}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Email:</td><td style="padding: 8px;">{safe["email"]}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Phone:</td><td style="padding: 8px;">{safe["phone"]}</td></tr>
                    <tr><td style="padding: 8px; font-weight: bold;">Service Type:</td><td style="padding: 8px;">{safe["service"]}</td></tr>
                </table>
                <h3>Message:</h3>
                <p style="background: #f5f5f5; padding: 15px; border-radius: 5px;">{safe["message"]}</p>
            </body>
            </html>
            """
            sent = await send_email(
                to=", ".join(recipients),
                subject=f"New Contact Form: {service_label} - {full_name}"[:200],
                html_body=admin_html,
                reply_to=email,
            )
            logger.info("Contact message %s emailed to ops: %s", contact_msg.id, bool(sent))
        except Exception:
            logger.exception("Failed to send admin notification for contact message %s", contact_msg.id)

        return contact_msg
