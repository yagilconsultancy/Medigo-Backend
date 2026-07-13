import logging
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from mediride_common.exceptions import RetryableError, ServiceUnavailableError

logger = logging.getLogger(__name__)
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_EMAIL_LOGO_PATH = _TEMPLATE_DIR / "email_logo.png"
_EMAIL_LOGO_CID = "medigo-logo"

# Template engine
_template_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    from_email: str | None = None,
    reply_to: str | None = None,
    smtp_username: str | None = None,
    smtp_password: str | None = None,
) -> bool:
    """Send email via SMTP."""
    sender = from_email or settings.EMAIL_FROM
    auth_username = smtp_username or settings.SMTP_USERNAME
    auth_password = smtp_password or settings.SMTP_PASSWORD
    missing_fields = [
        name
        for name, value in (
            ("SMTP_HOST", settings.SMTP_HOST),
            ("SMTP_PORT", settings.SMTP_PORT),
            ("SMTP_USERNAME", auth_username),
            ("SMTP_PASSWORD", auth_password),
            ("EMAIL_FROM", sender),
        )
        if not value
    ]
    if missing_fields:
        raise ServiceUnavailableError(
            f"SMTP is not fully configured: missing {', '.join(missing_fields)}"
        )

    message = MIMEMultipart("related")
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to

    alternative_message = MIMEMultipart("alternative")
    alternative_message.attach(MIMEText(html_body, "html"))
    message.attach(alternative_message)

    if f"cid:{_EMAIL_LOGO_CID}" in html_body and _EMAIL_LOGO_PATH.exists():
        with _EMAIL_LOGO_PATH.open("rb") as logo_file:
            logo_part = MIMEImage(logo_file.read(), _subtype="png")
        logo_part.add_header("Content-ID", f"<{_EMAIL_LOGO_CID}>")
        logo_part.add_header("Content-Disposition", "inline", filename=_EMAIL_LOGO_PATH.name)
        message.attach(logo_part)

    use_tls = settings.SMTP_USE_TLS or settings.SMTP_PORT == 465
    start_tls = settings.SMTP_STARTTLS and not use_tls

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=auth_username,
            password=auth_password,
            start_tls=start_tls,
            use_tls=use_tls,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        )
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.exception(
            "Failed SMTP send to %s via %s:%s (start_tls=%s, use_tls=%s): %s",
            to,
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            start_tls,
            use_tls,
            e,
        )
        raise RetryableError(
            f"SMTP delivery failed for {to} ({type(e).__name__}: {e})"
        ) from e


async def send_fleet_application_received_email(to: str, company_name: str) -> bool:
    """Send fleet application submission confirmation email."""
    subject = "MediGo - Fleet Application Received"
    sender = settings.PARTNERS_EMAIL_FROM
    reply_to = settings.PARTNERS_EMAIL_REPLY_TO
    smtp_username = settings.PARTNERS_SMTP_USERNAME or settings.SMTP_USERNAME
    smtp_password = settings.PARTNERS_SMTP_PASSWORD or settings.SMTP_PASSWORD

    try:
        template = _template_env.get_template("fleet_application_received.html")
        html = template.render(company_name=company_name)
    except Exception as e:
        logger.exception(
            "Failed to render fleet application received email for %s: %s",
            to,
            e,
        )
        html = f"""
        <html>
        <body>
            <p>Hello {company_name},</p>
            <p>Thank you for your interest in partnering with MediGo.</p>
            <p>We are pleased to confirm that your fleet application has been successfully submitted and received by our operations team.</p>
            <p>Our team will carefully review the information and supporting documents provided as part of your application. If additional information or clarification is required during the review process, a member of the MediGo team will contact you directly.</p>
            <p>While your application is being processed, we kindly recommend preparing the following to help ensure a smooth onboarding process if approved:</p>
            <ul>
                <li>Driver information and profiles</li>
                <li>Vehicle details and documentation</li>
                <li>Insurance records</li>
                <li>Licensing and compliance documents</li>
                <li>Operational contact information</li>
            </ul>
            <p>Once the review process is completed, you will receive an update regarding your application status and next steps.</p>
            <p>Thank you again for your interest in becoming a MediGo transportation partner.</p>
            <p>Warm regards,<br>MediGo Operations Team</p>
        </body>
        </html>
        """

    return await send_email(
        to=to,
        subject=subject,
        html_body=html,
        from_email=sender,
        reply_to=reply_to,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
    )


async def send_otp_email(to: str, otp_code: str) -> bool:
    """Send OTP verification email."""
    try:
        template = _template_env.get_template("otp_email.html")
        html = template.render(otp_code=otp_code)
    except Exception:
        # Fallback if template not found
        html = f"""
        <html>
        <body>
            <h2>MediGo - Verify Your Account</h2>
            <p>Your verification code is:</p>
            <h1 style="color: #3B5998; letter-spacing: 5px;">{otp_code}</h1>
            <p>This code expires in 5 minutes.</p>
            <p>If you didn't request this code, please ignore this email.</p>
        </body>
        </html>
        """
    return await send_email(to, "MediGo - Verification Code", html)


async def send_driver_invite_email(
    to: str, fleet_name: str, invite_token: str, temporary_password: str | None = None
) -> bool:
    """Send driver invitation email with an OTP-style invite code."""
    try:
        template = _template_env.get_template("driver_invite.html")
        html = template.render(
            fleet_name=fleet_name,
            invite_token=invite_token,
            email=to,
            temporary_password=temporary_password,
        )
    except Exception as e:
        logger.exception("Failed to render driver invite email for %s: %s", to, e)
        # Fallback if template not found
        password_section = ""
        if temporary_password:
            password_section = f"""
            <h3>Your Login Credentials</h3>
            <p><strong>Email:</strong> {to}</p>
            <p><strong>Password:</strong> {temporary_password}</p>
            <p style="color: #e74c3c;">Please change your password after your first login.</p>
            """
        html = f"""
        <html>
        <body>
            <h2>MediGo - Driver Invitation Code</h2>
            <p><strong>{fleet_name}</strong> has invited you to join their driver network.</p>
            {password_section}
            <p>Use the code below in the MediGo Driver app to continue your registration:</p>
            <h3 style="color: #3B5998; letter-spacing: 2px; word-break: break-all;">{invite_token}</h3>
            <p>This invitation expires in 7 days.</p>
        </body>
        </html>
        """
    return await send_email(
        to,
        f"MediGo - Driver Invitation Code from {fleet_name}",
        html,
    )


async def send_account_reactivation_email(
    to: str, name: str, reactivation_link: str
) -> bool:
    """Email a driver a link to reactivate after their login email was changed."""
    try:
        template = _template_env.get_template("account_reactivation.html")
        html = template.render(name=name, reactivation_link=reactivation_link)
    except Exception as e:
        logger.exception("Failed to render reactivation email for %s: %s", to, e)
        html = f"""
        <html>
        <body>
            <h2>MediGo - Reactivate Your Account</h2>
            <p>Hi {name},</p>
            <p>Your MediGo login email was updated to this address. For security,
            your account has been temporarily deactivated.</p>
            <p>Click the button below to verify this email and reactivate your account:</p>
            <p><a href="{reactivation_link}">Reactivate my account</a></p>
            <p>This link expires in 7 days. If you didn't expect this, contact support.</p>
        </body>
        </html>
        """
    return await send_email(
        to,
        "MediGo - Reactivate Your Account",
        html,
    )


async def send_password_reset_email(to: str, reset_token: str) -> bool:
    """Send password reset email."""
    try:
        template = _template_env.get_template("password_reset.html")
        html = template.render(reset_token=reset_token)
    except Exception as e:
        logger.exception("Failed to render password reset email for %s: %s", to, e)
        html = f"""
        <html>
        <body>
            <h2>MediGo - Reset Your Password</h2>
            <p>Use the following code to reset your password:</p>
            <h3 style="color: #3B5998; letter-spacing: 2px; word-break: break-all;">{reset_token}</h3>
            <p>This code expires in 30 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
        </html>
        """
    return await send_email(to, "MediGo - Password Reset", html)


async def send_admin_invite_email(
    to: str,
    full_name: str,
    role_display_name: str,
    temporary_password: str,
    invited_by_name: str,
) -> bool:
    """Send admin credentials email."""
    try:
        template = _template_env.get_template("admin_invite.html")
        html = template.render(
            email=to,
            full_name=full_name,
            role_display_name=role_display_name,
            temporary_password=temporary_password,
            invited_by_name=invited_by_name,
        )
    except Exception as e:
        logger.exception("Failed to render admin invite email for %s: %s", to, e)
        # Fallback if template not found
        html = f"""
        <html>
        <body>
            <h2>Welcome to the MediGo Team!</h2>
            <p>Hi <strong>{full_name}</strong>,</p>
            <p>You've been invited to join the MediGo admin team as a <strong>{role_display_name}</strong>.</p>
            <p><strong>Invited by:</strong> {invited_by_name}</p>
            <h3>Your Login Credentials</h3>
            <p><strong>Email:</strong> {to}</p>
            <p><strong>Password:</strong> {temporary_password}</p>
            <p style="color: #dc2626; font-weight: bold;">Please log in and change your password immediately.</p>
        </body>
        </html>
        """
    return await send_email(to, "MediGo - Your Admin Account Credentials", html)


async def send_ride_notification_email(
    to: str,
    name: str,
    subject: str,
    title: str,
    body: str,
    ride_details: dict | None = None,
) -> bool:
    """Send ride notification email (generic template for all ride events)."""
    ride_id_short = ride_details.get('ride_id', 'N/A')[:8] if ride_details else ''

    try:
        template = _template_env.get_template("ride_notification.html")
        html = template.render(
            name=name,
            title=title,
            body=body,
            ride_details=ride_details,
            ride_id_short=ride_id_short,
        )
    except Exception as e:
        logger.exception("Failed to render ride notification email for %s: %s", to, e)
        # Fallback if template not found
        ride_info = ""
        if ride_details:
            ride_info = f"""
            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="margin-top: 0;">Ride Details</h3>
                <p><strong>Ride ID:</strong> #{ride_id_short}</p>
                <p><strong>Pickup:</strong> {ride_details.get('pickup_address', 'N/A')}</p>
                <p><strong>Destination:</strong> {ride_details.get('destination_address', 'N/A')}</p>
                <p><strong>Scheduled:</strong> {ride_details.get('scheduled_at', 'N/A')}</p>
            </div>
            """
        html = f"""
        <html>
        <body>
            <h2>MediGo - {title}</h2>
            <p>Hi {name},</p>
            <p>{body}</p>
            {ride_info}
            <p>You can view your ride details in the MediGo app.</p>
            <p>Thank you for choosing MediGo!</p>
        </body>
        </html>
        """
    return await send_email(to, subject, html)


async def send_admin_message_email(
    to: str,
    recipient_name: str,
    title: str,
    message: str,
    sent_by_name: str | None = None,
) -> bool:
    """Send an admin message notification email to a user."""
    subject = f"MediGo - {title}"
    try:
        template = _template_env.get_template("admin_message.html")
        html = template.render(
            recipient_name=recipient_name,
            title=title,
            message=message,
            sent_by_name=sent_by_name,
        )
    except Exception as e:
        logger.exception("Failed to render admin message email for %s: %s", to, e)
        sent_by_section = f'<p style="color: #888; font-size: 13px;">Sent by: {sent_by_name}</p>' if sent_by_name else ''
        html = f"""
        <html>
        <body>
            <h2>MediGo - {title}</h2>
            <p>Hi {recipient_name},</p>
            <p>You have a new message from the MediGo admin team:</p>
            <div style="background-color: #f0f4ff; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #3B5998;">
                <p>{message}</p>
            </div>
            {sent_by_section}
            <p>If you have any questions, please reply through the MediGo app.</p>
        </body>
        </html>
        """
    return await send_email(to, subject, html)


async def send_fleet_info_request_email(
    to: str, company_name: str, message: str
) -> bool:
    """Send email to fleet applicant requesting additional information."""
    try:
        template = _template_env.get_template("fleet_info_request.html")
        html = template.render(company_name=company_name, admin_message=message)
    except Exception as e:
        logger.exception("Failed to render fleet info request email for %s: %s", to, e)
        html = f"""
        <html>
        <body>
            <h2>MediGo - Additional Information Required</h2>
            <p>Hi {company_name},</p>
            <p>We've reviewed your fleet application and need some additional information before we can proceed:</p>
            <div style="background-color: #f0f4ff; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #3B5998;">
                <p>{message}</p>
            </div>
            <p>Please log in to your MediGo account and update your application with the requested information.</p>
        </body>
        </html>
        """
    return await send_email(to, "MediGo - Additional Information Required for Your Fleet Application", html)


async def send_fleet_application_approved_email(to: str, company_name: str) -> bool:
    """Send email to fleet applicant when the application is approved."""
    subject = "MediGo - Fleet Application Approved"
    sender = settings.PARTNERS_EMAIL_FROM
    reply_to = settings.PARTNERS_EMAIL_REPLY_TO
    smtp_username = settings.PARTNERS_SMTP_USERNAME or settings.SMTP_USERNAME
    smtp_password = settings.PARTNERS_SMTP_PASSWORD or settings.SMTP_PASSWORD

    try:
        template = _template_env.get_template("fleet_application_approved.html")
        html = template.render(company_name=company_name)
    except Exception as e:
        logger.exception("Failed to render fleet application approved email for %s: %s", to, e)
        html = f"""
        <html>
        <body>
            <p>Hello {company_name},</p>
            <p>Great news. Your MediGo fleet application has been approved.</p>
            <p>Our operations team will contact you shortly with onboarding steps and next actions.</p>
            <p>Thank you for partnering with MediGo.</p>
            <p>Warm regards,<br>MediGo Operations Team</p>
        </body>
        </html>
        """

    return await send_email(
        to=to,
        subject=subject,
        html_body=html,
        from_email=sender,
        reply_to=reply_to,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
    )


async def send_fleet_application_rejected_email(
    to: str,
    company_name: str,
    reason: str,
) -> bool:
    """Send email to fleet applicant when the application is rejected."""
    subject = "MediGo - Fleet Application Update"
    sender = settings.PARTNERS_EMAIL_FROM
    reply_to = settings.PARTNERS_EMAIL_REPLY_TO
    smtp_username = settings.PARTNERS_SMTP_USERNAME or settings.SMTP_USERNAME
    smtp_password = settings.PARTNERS_SMTP_PASSWORD or settings.SMTP_PASSWORD

    try:
        template = _template_env.get_template("fleet_application_rejected.html")
        html = template.render(company_name=company_name, reason=reason)
    except Exception as e:
        logger.exception("Failed to render fleet application rejected email for %s: %s", to, e)
        html = f"""
        <html>
        <body>
            <p>Hello {company_name},</p>
            <p>Thank you for applying to partner with MediGo.</p>
            <p>After review, we are unable to proceed with your application at this time.</p>
            <p><strong>Reason:</strong> {reason}</p>
            <p>You may submit a new application after addressing the item above.</p>
            <p>Warm regards,<br>MediGo Operations Team</p>
        </body>
        </html>
        """

    return await send_email(
        to=to,
        subject=subject,
        html_body=html,
        from_email=sender,
        reply_to=reply_to,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
    )


async def send_payment_receipt_email(
    to: str,
    name: str,
    receipt: dict,
) -> bool:
    """Send a payment receipt email after a successful ride charge."""
    trip_number = receipt.get("trip_number", "Trip Receipt")
    subject = f"medigo - Receipt for {trip_number}"

    template_context = {
        "name": name,
        "trip_number": trip_number,
        "currency": receipt.get("currency", "CAD"),
        "total_fare": f"{float(receipt.get('total_fare') or 0):.2f}",
        "ride_date": receipt.get("ride_date") or "N/A",
        "pickup_address": receipt.get("pickup_address") or "N/A",
        "destination_address": receipt.get("destination_address") or "N/A",
        "payment_method_type": receipt.get("payment_method_type") or "Card",
        "payment_method_last_four": receipt.get("payment_method_last_four") or "N/A",
        "paid_at": receipt.get("paid_at") or "Processed successfully",
    }

    try:
        template = _template_env.get_template("payment_receipt.html")
        html = template.render(**template_context)
    except Exception as e:
        logger.exception("Failed to render payment receipt email for %s: %s", to, e)
        html = f"""
        <html>
        <body>
            <h2>MediGo - Payment Receipt</h2>
            <p>Hi {name},</p>
            <p>Your Stripe payment was successful.</p>
            <p><strong>Trip number:</strong> {template_context['trip_number']}</p>
            <p><strong>Total:</strong> {template_context['currency']} {template_context['total_fare']}</p>
            <p><strong>Payment method:</strong> {template_context['payment_method_type']} ending in {template_context['payment_method_last_four']}</p>
        </body>
        </html>
        """
    return await send_email(to, subject, html)
