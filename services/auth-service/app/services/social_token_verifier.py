"""Verify Apple and Google identity tokens on the server.

The app or website gets a signed identity token from the provider. We never
trust what the client says about who signed in: we check the signature against
the provider's published public keys, and that the token was issued by the
provider, for one of our own client ids, and has not expired.
"""

import hmac
import logging
import time
from dataclasses import dataclass

import httpx
from jose import JWTError, jwt

from mediride_common.exceptions import (
    AuthenticationError,
    ServiceUnavailableError,
    ValidationError,
)

logger = logging.getLogger(__name__)

PROVIDERS = ("google", "apple")

_JWKS_URLS = {
    "google": "https://www.googleapis.com/oauth2/v3/certs",
    "apple": "https://appleid.apple.com/auth/keys",
}
_ISSUERS = {
    "google": ("https://accounts.google.com", "accounts.google.com"),
    "apple": ("https://appleid.apple.com",),
}
_JWKS_TTL_SECONDS = 3600
_REQUEST_TIMEOUT = 10.0


@dataclass(frozen=True)
class SocialClaims:
    provider: str
    subject: str
    email: str | None
    email_verified: bool
    is_private_email: bool
    first_name: str | None = None
    last_name: str | None = None


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


def parse_client_ids(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


class SocialTokenVerifier:
    def __init__(self, google_client_ids: str, apple_client_ids: str, fetch_jwks=None):
        self._client_ids = {
            "google": parse_client_ids(google_client_ids),
            "apple": parse_client_ids(apple_client_ids),
        }
        self._fetch_jwks = fetch_jwks or self._http_fetch_jwks
        self._cache: dict[str, tuple[float, list[dict]]] = {}

    def is_enabled(self, provider: str) -> bool:
        return bool(self._client_ids.get(provider))

    @staticmethod
    async def _http_fetch_jwks(url: str) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
                response = await client.get(url)
        except (httpx.ConnectError, httpx.TimeoutException):
            raise ServiceUnavailableError("Sign-in provider is unavailable")
        if response.status_code != 200:
            raise ServiceUnavailableError("Sign-in provider is unavailable")
        return response.json().get("keys", [])

    async def _keys(self, provider: str, force: bool = False) -> list[dict]:
        cached = self._cache.get(provider)
        if cached and not force and time.time() - cached[0] < _JWKS_TTL_SECONDS:
            return cached[1]
        keys = await self._fetch_jwks(_JWKS_URLS[provider])
        self._cache[provider] = (time.time(), keys)
        return keys

    async def verify(
        self, provider: str, id_token: str, nonce: str | None = None
    ) -> SocialClaims:
        if provider not in PROVIDERS:
            raise ValidationError("Unsupported sign-in provider")
        if not self.is_enabled(provider):
            raise ServiceUnavailableError(
                f"Sign in with {provider.capitalize()} is not available yet"
            )

        failure = AuthenticationError(
            f"We could not verify your {provider.capitalize()} sign-in"
        )
        try:
            header = jwt.get_unverified_header(id_token)
        except JWTError:
            raise failure
        if header.get("alg") != "RS256" or not header.get("kid"):
            raise failure

        key = next((k for k in await self._keys(provider) if k.get("kid") == header["kid"]), None)
        if key is None:
            # The provider may have rotated its keys; look once more.
            key = next(
                (k for k in await self._keys(provider, force=True) if k.get("kid") == header["kid"]),
                None,
            )
        if key is None:
            raise failure

        try:
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                options={"verify_aud": False, "verify_iss": False, "verify_at_hash": False},
            )
        except JWTError:
            raise failure

        if claims.get("iss") not in _ISSUERS[provider]:
            raise failure
        audience = claims.get("aud")
        audiences = audience if isinstance(audience, list) else [audience]
        if not any(a in self._client_ids[provider] for a in audiences):
            raise failure
        if nonce is not None and not hmac.compare_digest(
            str(claims.get("nonce", "")), nonce
        ):
            raise failure
        subject = claims.get("sub")
        if not subject:
            raise failure

        email = claims.get("email")
        return SocialClaims(
            provider=provider,
            subject=str(subject),
            email=email.strip().lower() if email else None,
            email_verified=_as_bool(claims.get("email_verified", False)),
            is_private_email=_as_bool(claims.get("is_private_email", False)),
            first_name=claims.get("given_name"),
            last_name=claims.get("family_name"),
        )
