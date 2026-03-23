import logging

import aioboto3
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

logger = logging.getLogger(__name__)

# Template engine
_template_env = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html"]),
)

_session = aioboto3.Session()


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send email via AWS SES."""
    if not settings.AWS_ACCESS_KEY_ID:
        logger.warning(f"AWS SES not configured. Would send to {to}: {subject}")
        logger.info(f"Email body preview: {html_body[:200]}...")
        return True

    try:
        async with _session.client(
            "ses",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        ) as ses:
            kwargs = {
                "Source": settings.EMAIL_FROM,
                "Destination": {"ToAddresses": [to]},
                "Message": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            }
            if settings.SES_CONFIGURATION_SET:
                kwargs["ConfigurationSetName"] = settings.SES_CONFIGURATION_SET

            await ses.send_email(**kwargs)

        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


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
            <h2>MediRide - Verify Your Account</h2>
            <p>Your verification code is:</p>
            <h1 style="color: #3B5998; letter-spacing: 5px;">{otp_code}</h1>
            <p>This code expires in 5 minutes.</p>
            <p>If you didn't request this code, please ignore this email.</p>
        </body>
        </html>
        """
    return await send_email(to, "MediRide - Verification Code", html)


async def send_driver_invite_email(
    to: str, business_name: str, invite_token: str
) -> bool:
    """Send driver invitation email."""
    try:
        template = _template_env.get_template("driver_invite.html")
        html = template.render(
            business_name=business_name,
            invite_token=invite_token,
        )
    except Exception:
        # Fallback if template not found
        html = f"""
        <html>
        <body>
            <h2>You're Invited to Drive with MediRide!</h2>
            <p><strong>{business_name}</strong> has invited you to join their driver network.</p>
            <p>Download the MediRide Driver app and use this invitation code to sign up:</p>
            <h3 style="color: #3B5998;">{invite_token}</h3>
            <p>This invitation expires in 7 days.</p>
        </body>
        </html>
        """
    return await send_email(to, f"MediRide - Driver Invitation from {business_name}", html)


async def send_password_reset_email(to: str, reset_token: str) -> bool:
    """Send password reset email."""
    try:
        template = _template_env.get_template("password_reset.html")
        html = template.render(reset_token=reset_token)
    except Exception:
        html = f"""
        <html>
        <body>
            <h2>MediRide - Reset Your Password</h2>
            <p>Use the following code to reset your password:</p>
            <h3 style="color: #3B5998;">{reset_token}</h3>
            <p>This code expires in 30 minutes.</p>
            <p>If you didn't request this, please ignore this email.</p>
        </body>
        </html>
        """
    return await send_email(to, "MediRide - Password Reset", html)
