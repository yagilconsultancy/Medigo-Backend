"""Sign in with Apple / Google: token checks, account creation and linking."""

import os
import sys
import time
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

os.environ["DEBUG"] = "false"
os.environ["ENVIRONMENT"] = "development"

sys.modules.setdefault(
    "aio_pika",
    types.SimpleNamespace(
        connect_robust=None,
        ExchangeType=types.SimpleNamespace(TOPIC="topic", FANOUT="fanout"),
        Message=object,
        DeliveryMode=types.SimpleNamespace(PERSISTENT=2),
    ),
)
sys.modules.setdefault(
    "aio_pika.abc",
    types.SimpleNamespace(
        AbstractChannel=object,
        AbstractConnection=object,
        AbstractExchange=object,
        AbstractIncomingMessage=object,
    ),
)

import app.services.auth_service as auth_service_module
from app.config import settings
from app.models.social_identity import SocialIdentity
from app.services.auth_service import AuthService
from app.services.social_token_verifier import SocialTokenVerifier
from mediride_common.auth.jwt_handler import JWTHandler
from mediride_common.auth.models import TokenPair
from mediride_common.exceptions import (
    AuthenticationError,
    ConflictError,
    ServiceUnavailableError,
)
from mediride_common.schemas.enums import UserRole

GOOGLE_ID = "google-client-1"
APPLE_ID = "com.example.medigo"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(key):
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _public_jwk(key, kid="k1"):
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    d = jwk.construct(pub, "RS256").to_dict()
    d["kid"] = kid
    return d


def _token(provider="google", key=_KEY, kid="k1", **overrides):
    claims = {
        "iss": "https://accounts.google.com"
        if provider == "google"
        else "https://appleid.apple.com",
        "aud": GOOGLE_ID if provider == "google" else APPLE_ID,
        "sub": "subject-123",
        "email": "Rider@Example.com",
        "email_verified": True,
        "exp": int(time.time()) + 600,
        "iat": int(time.time()),
    }
    claims.update(overrides)
    return jwt.encode(claims, _pem(key), algorithm="RS256", headers={"kid": kid})


def _verifier():
    async def fetch(url):
        return [_public_jwk(_KEY)]

    return SocialTokenVerifier(GOOGLE_ID, APPLE_ID, fetch_jwks=fetch)


# --------------------------- token checks ---------------------------


@pytest.mark.asyncio
async def test_valid_google_token_is_accepted():
    claims = await _verifier().verify("google", _token())
    assert claims.subject == "subject-123"
    assert claims.email == "rider@example.com"
    assert claims.email_verified is True


@pytest.mark.asyncio
async def test_valid_apple_token_with_string_flags():
    token = _token("apple", email_verified="true", is_private_email="true")
    claims = await _verifier().verify("apple", token)
    assert claims.email_verified is True
    assert claims.is_private_email is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "someone-elses-app"},
        {"iss": "https://evil.example.com"},
        {"exp": int(time.time()) - 10},
        {"sub": ""},
    ],
)
async def test_bad_claims_are_rejected(overrides):
    with pytest.raises(AuthenticationError):
        await _verifier().verify("google", _token(**overrides))


@pytest.mark.asyncio
async def test_token_signed_by_another_key_is_rejected():
    with pytest.raises(AuthenticationError):
        await _verifier().verify("google", _token(key=_OTHER_KEY))


@pytest.mark.asyncio
async def test_unknown_key_id_is_rejected():
    with pytest.raises(AuthenticationError):
        await _verifier().verify("google", _token(kid="nope"))


@pytest.mark.asyncio
async def test_unsigned_token_is_rejected():
    forged = jwt.encode({"sub": "x", "aud": GOOGLE_ID}, "secret", algorithm="HS256")
    with pytest.raises(AuthenticationError):
        await _verifier().verify("google", forged)


@pytest.mark.asyncio
async def test_nonce_must_match_when_given():
    token = _token(nonce="abc")
    assert (await _verifier().verify("google", token, nonce="abc")).subject
    with pytest.raises(AuthenticationError):
        await _verifier().verify("google", token, nonce="different")


@pytest.mark.asyncio
async def test_provider_without_client_ids_is_switched_off():
    verifier = SocialTokenVerifier("", "", fetch_jwks=AsyncMock())
    with pytest.raises(ServiceUnavailableError):
        await verifier.verify("google", _token())


# --------------------------- account logic ---------------------------


def _service(existing=None, identity=None, by_id=None):
    credential_repo = MagicMock()
    credential_repo.get_by_email = AsyncMock(return_value=existing)
    credential_repo.get_by_id = AsyncMock(return_value=by_id or existing)
    async def _create(credential):
        credential.id = uuid4()  # the real repo gets this from the flush
        return credential

    credential_repo.create = AsyncMock(side_effect=_create)
    credential_repo.increment_failed_attempts = AsyncMock()
    credential_repo.reset_failed_attempts = AsyncMock()
    credential_repo.lock_account = AsyncMock()
    credential_repo.session = MagicMock()
    credential_repo.session.commit = AsyncMock()
    social_repo = MagicMock()
    social_repo.get = AsyncMock(return_value=identity)
    social_repo.create = AsyncMock()
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    jwt_handler = JWTHandler(
        secret_key=settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
        access_token_expire_minutes=30,
        refresh_token_expire_days=7,
    )
    service = AuthService(
        credential_repo=credential_repo,
        token_repo=MagicMock(),
        otp_service=MagicMock(),
        jwt_handler=jwt_handler,
        publisher=publisher,
        social_repo=social_repo,
        social_verifier=_verifier(),
    )
    service.token_repo.create = AsyncMock()
    service._max_failed_attempts = AsyncMock(return_value=5)
    return service


def _rider(**kw):
    base = dict(
        id=uuid4(), email="rider@example.com", phone=None,
        password_hash="hashed:RealPass123!", is_active=True, is_verified=True,
        role=UserRole.RIDER, locked_until=None, failed_attempts=0,
        business_id=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _stub_password_verify(monkeypatch):
    monkeypatch.setattr(
        auth_service_module,
        "verify_password",
        lambda password, password_hash: password_hash == f"hashed:{password}",
    )


@pytest.mark.asyncio
async def test_new_identity_creates_verified_rider_and_signs_in():
    service = _service()
    pair = await service.social_login("google", _token())
    created = service.credential_repo.create.await_args.args[0]
    assert created.role == UserRole.RIDER
    assert created.is_verified is True
    assert created.email == "rider@example.com"
    assert created.phone is None
    service.social_repo.create.assert_awaited_once()
    assert service.publisher.publish.await_count == 2
    assert pair.access_token and pair.role == UserRole.RIDER


@pytest.mark.asyncio
async def test_known_identity_signs_in_without_creating_anything():
    rider = _rider()
    identity = SocialIdentity(user_id=rider.id, provider="google", subject="subject-123")
    service = _service(existing=rider, identity=identity)
    pair = await service.social_login("google", _token())
    assert pair.access_token
    service.credential_repo.create.assert_not_awaited()
    service.social_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_email_is_never_linked_without_the_password():
    service = _service(existing=_rider())
    with pytest.raises(ConflictError) as exc:
        await service.social_login("google", _token())
    assert exc.value.details["code"] == "account_link_required"
    assert exc.value.details["link_token"]
    service.social_repo.create.assert_not_awaited()
    service.credential_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_non_rider_email_cannot_be_taken_over():
    service = _service(existing=_rider(role=UserRole.DRIVER))
    with pytest.raises(ConflictError) as exc:
        await service.social_login("google", _token())
    assert not (exc.value.details or {}).get("link_token")
    service.social_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_unverified_provider_email_is_refused():
    service = _service()
    with pytest.raises(AuthenticationError):
        await service.social_login("google", _token(email_verified=False))
    service.credential_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_private_relay_email_is_not_matched_to_existing_account():
    service = _service(existing=_rider(email="abc@privaterelay.appleid.com"))
    token = _token("apple", email="abc@privaterelay.appleid.com", is_private_email="true")
    await service.social_login("apple", token)
    service.credential_repo.get_by_email.assert_not_awaited()
    service.credential_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_deactivated_or_non_rider_identity_cannot_sign_in():
    for rider in (_rider(is_active=False), _rider(role=UserRole.ADMIN)):
        identity = SocialIdentity(user_id=rider.id, provider="google", subject="subject-123")
        service = _service(existing=rider, identity=identity)
        with pytest.raises(AuthenticationError):
            await service.social_login("google", _token())


@pytest.mark.asyncio
async def test_link_with_correct_password_links_and_signs_in():
    rider = _rider()
    service = _service(existing=rider)
    with pytest.raises(ConflictError) as exc:
        await service.social_login("google", _token())
    link_token = exc.value.details["link_token"]
    pair = await service.social_link(link_token, "RealPass123!")
    assert pair.access_token
    args = service.social_repo.create.await_args.args
    assert args[0] == rider.id and args[1] == "google" and args[2] == "subject-123"


@pytest.mark.asyncio
async def test_link_with_wrong_password_is_refused_and_counted():
    rider = _rider()
    service = _service(existing=rider)
    with pytest.raises(ConflictError) as exc:
        await service.social_login("google", _token())
    with pytest.raises(AuthenticationError):
        await service.social_link(exc.value.details["link_token"], "wrong")
    service.credential_repo.increment_failed_attempts.assert_awaited_once()
    service.social_repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_link_token_is_not_a_login_token_and_junk_is_refused():
    rider = _rider()
    service = _service(existing=rider)
    with pytest.raises(ConflictError) as exc:
        await service.social_login("google", _token())
    link_token = exc.value.details["link_token"]
    with pytest.raises(Exception):
        service.jwt_handler.decode_to_claims(link_token)
    # An ordinary access token cannot be used as a link token.
    access = service.jwt_handler.create_token_pair(
        user_id=str(rider.id), role="rider", business_id=None, email=rider.email
    ).access_token
    with pytest.raises(AuthenticationError):
        await service.social_link(access, "RealPass123!")
    with pytest.raises(AuthenticationError):
        await service.social_link("not-a-token-at-all-just-junk", "x")
