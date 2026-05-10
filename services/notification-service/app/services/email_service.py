import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from mediride_common.exceptions import RetryableError, ServiceUnavailableError

logger = logging.getLogger(__name__)
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# Template engine
_template_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send email via SMTP."""
    missing_fields = [
        name
        for name, value in (
            ("SMTP_HOST", settings.SMTP_HOST),
            ("SMTP_PORT", settings.SMTP_PORT),
            ("SMTP_USERNAME", settings.SMTP_USERNAME),
            ("SMTP_PASSWORD", settings.SMTP_PASSWORD),
            ("EMAIL_FROM", settings.EMAIL_FROM),
        )
        if not value
    ]
    if missing_fields:
        raise ServiceUnavailableError(
            f"SMTP is not fully configured: missing {', '.join(missing_fields)}"
        )

    message = MIMEMultipart("alternative")
    message["From"] = settings.EMAIL_FROM
    message["To"] = to
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))

    use_tls = settings.SMTP_USE_TLS or settings.SMTP_PORT == 465
    start_tls = settings.SMTP_STARTTLS and not use_tls

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME,
            password=settings.SMTP_PASSWORD,
            start_tls=start_tls,
            use_tls=use_tls,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        )
        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", to, e)
        raise RetryableError(f"SMTP delivery failed for {to}") from e


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
    invite_token: str,
    invited_by_name: str,
) -> bool:
    """Send admin invitation email."""
    try:
        template = _template_env.get_template("admin_invite.html")
        html = template.render(
            email=to,
            full_name=full_name,
            role_display_name=role_display_name,
            invite_token=invite_token,
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
            <p>Use this invitation code to register:</p>
            <h3 style="color: #8B5CF6;">{invite_token}</h3>
            <p><strong>Email:</strong> {to}</p>
            <p style="color: #dc2626;">This invitation expires in 7 days.</p>
        </body>
        </html>
        """
    return await send_email(to, "MediGo - Admin Invitation", html)


async def send_ride_notification_email(
    to: str,
    name: str,
    subject: str,
    title: str,
    body: str,
    ride_details: dict | None = None,
) -> bool:
    """Send ride notification email (generic template for all ride events)."""
    ride_info = ""
    if ride_details:
        ride_info = f"""
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3 style="margin-top: 0;">Ride Details</h3>
            <p><strong>Ride ID:</strong> #{ride_details.get('ride_id', 'N/A')[:8]}</p>
            <p><strong>Pickup:</strong> {ride_details.get('pickup_address', 'N/A')}</p>
            <p><strong>Destination:</strong> {ride_details.get('destination_address', 'N/A')}</p>
            <p><strong>Scheduled:</strong> {ride_details.get('scheduled_at', 'N/A')}</p>
        </div>
        """

    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #3B5998; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #ffffff; }}
            .button {{ background-color: #3B5998; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }}
            .footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>MediGo</h1>
            </div>
            <div class="content">
                <p>Hi {name},</p>
                <h2>{title}</h2>
                <p>{body}</p>
                {ride_info}
                <p>You can view your ride details in the MediGo app.</p>
                <p>Thank you for choosing MediGo!</p>
            </div>
            <div class="footer">
                <p>&copy; 2026 MediGo. All rights reserved.</p>
                <p>This is an automated notification. Please do not reply to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return await send_email(to, subject, html)
