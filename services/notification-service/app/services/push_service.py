import logging

logger = logging.getLogger(__name__)

try:
    from exponent_server_sdk import (
        DeviceNotRegisteredError,
        PushClient,
        PushMessage,
        PushServerError,
    )
    _push_client = PushClient()
    _expo_available = True
except ImportError:
    logger.warning("exponent-server-sdk not installed — push notifications disabled")
    _push_client = None
    _expo_available = False


async def send_expo_push(
    push_token: str,
    title: str,
    body: str,
    data: dict | None = None,
) -> bool:
    """Send a push notification via Expo's push service.

    Returns True if the notification was sent successfully.
    Falls back gracefully if the Expo SDK is not installed.
    """
    if not _expo_available:
        logger.debug("Expo SDK not available, skipping push for: %s", title)
        return False

    if not PushClient.is_exponent_push_token(push_token):
        logger.warning("Invalid Expo push token: %s", push_token)
        return False

    try:
        response = _push_client.publish(
            PushMessage(
                to=push_token,
                title=title,
                body=body,
                data=data or {},
                sound="default",
            )
        )
        response.validate_response()
        logger.info("Expo push sent to token %s: %s", push_token[:20], title)
        return True
    except DeviceNotRegisteredError:
        logger.warning("Device not registered for token: %s", push_token[:20])
        return False
    except PushServerError as e:
        logger.error("Expo push server error: %s", e)
        return False
    except Exception as e:
        logger.exception("Failed to send Expo push notification: %s", e)
        return False
