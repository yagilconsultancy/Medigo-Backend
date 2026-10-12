"""Shared secret for service-to-service calls.

Backend services call each other on private ``/internal/...`` routes. Every
such call carries two headers:

* ``X-Internal-Service``: the name of the calling service (used in logs).
* ``X-Internal-Token``: a shared secret taken from ``INTERNAL_SERVICE_TOKEN``.

Receivers check the secret according to ``INTERNAL_AUTH_MODE``:

* ``log`` (default): a missing or wrong secret is allowed but logged, so any
  caller that was missed shows up in the logs before anything is blocked.
* ``enforce``: a missing or wrong secret gets 403. The built-in development
  secret is refused in this mode, so it can never protect a real server.
* ``off``: only the old check (some caller name must be present).
"""
import hmac
import logging
import os

from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

INTERNAL_SERVICE_HEADER = "X-Internal-Service"
INTERNAL_TOKEN_HEADER = "X-Internal-Token"
DEV_INTERNAL_TOKEN = "dev-internal-token-change-in-production"

MODE_OFF = "off"
MODE_LOG = "log"
MODE_ENFORCE = "enforce"


def internal_token() -> str:
    return os.environ.get("INTERNAL_SERVICE_TOKEN") or DEV_INTERNAL_TOKEN


def internal_auth_mode() -> str:
    mode = (os.environ.get("INTERNAL_AUTH_MODE") or MODE_LOG).strip().lower()
    return mode if mode in (MODE_OFF, MODE_LOG, MODE_ENFORCE) else MODE_LOG


def internal_headers(service_name: str, token: str | None = None) -> dict[str, str]:
    """Headers a service sends when it calls another service's /internal routes."""
    return {
        INTERNAL_SERVICE_HEADER: service_name,
        INTERNAL_TOKEN_HEADER: token or internal_token(),
    }


def require_internal_service(
    request: Request,
    x_internal_service: str | None = Header(None),
    x_internal_token: str | None = Header(None),
) -> str:
    """FastAPI dependency for /internal routes. Returns the caller's name."""
    if not x_internal_service:
        raise HTTPException(status_code=403, detail="Internal access only")

    mode = internal_auth_mode()
    if mode == MODE_OFF:
        return x_internal_service

    expected = internal_token()
    token_ok = bool(x_internal_token) and hmac.compare_digest(
        x_internal_token.encode(), expected.encode()
    )

    if mode == MODE_ENFORCE:
        if expected == DEV_INTERNAL_TOKEN:
            logger.error(
                "INTERNAL_AUTH_MODE=enforce but INTERNAL_SERVICE_TOKEN is still the "
                "built-in development value; refusing internal call to %s",
                request.url.path,
            )
            raise HTTPException(status_code=403, detail="Internal access only")
        if not token_ok:
            logger.warning(
                "Internal call refused: caller=%s path=%s (missing or wrong token)",
                x_internal_service,
                request.url.path,
            )
            raise HTTPException(status_code=403, detail="Internal access only")
        return x_internal_service

    if not token_ok:
        logger.warning(
            "INTERNAL_CALL_WITHOUT_VALID_TOKEN caller=%s path=%s",
            x_internal_service,
            request.url.path,
        )
    return x_internal_service
