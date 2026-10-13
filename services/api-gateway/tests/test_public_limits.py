import pytest
from starlette.requests import Request

from app.config import GatewaySettings
from app.middleware import public_limits
from app.routes.proxy import _is_public_path


def _request(method="POST", path="/auth/login", headers=None, client=("10.0.0.9", 1234)):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": raw,
        "client": client,
        "query_string": b"",
    }
    return Request(scope)


def test_every_limited_path_is_a_public_path():
    # Limits only make sense on paths anyone can call. If a path is renamed or
    # made private, this reminds us to update the rule table.
    for (_method, path) in public_limits._RULES:
        assert _is_public_path(path), path


def test_every_rule_points_at_a_defined_group():
    for group in public_limits._RULES.values():
        assert group in public_limits.GROUP_LIMITS


@pytest.mark.parametrize(
    "method,path,group",
    [
        ("POST", "/auth/login", "login"),
        ("POST", "/auth/admin/login", "login"),
        ("POST", "/auth/login/", "login"),
        ("POST", "/auth/social/login", "login"),
        ("POST", "/auth/social/link", "login"),
        ("POST", "/auth/forgot-password", "send_code"),
        ("POST", "/auth/resend-otp", "send_code"),
        ("POST", "/auth/verify-otp", "check_code"),
        ("POST", "/users/public/fleet/apply", "fleet_apply"),
        ("POST", "/rides/public/guest-sessions", "public_form"),
        ("GET", "/locations/public/check-address", "maps_lookup"),
        ("post", "/auth/register", "register"),
    ],
)
def test_rule_lookup(method, path, group):
    assert public_limits.limit_group_for(method, path) == group


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/auth/login"),  # only POST is limited
        ("POST", "/auth/logout"),
        ("POST", "/auth/refresh"),  # the app refreshes tokens often
        ("GET", "/rides/public/guest-sessions/abc"),
        ("POST", "/rides/123/share"),
        ("POST", "/auth/admin/login-history"),
    ],
)
def test_unlimited_requests(method, path):
    assert public_limits.limit_group_for(method, path) is None


def test_client_ip_prefers_nginx_header():
    req = _request(headers={"X-Real-IP": "203.0.113.7", "X-Forwarded-For": "1.2.3.4"})
    assert public_limits.client_ip(req) == "203.0.113.7"


def test_client_ip_falls_back_to_socket():
    assert public_limits.client_ip(_request()) == "10.0.0.9"


@pytest.fixture
def calls(monkeypatch):
    seen = []

    async def fake_check(key, max_requests=None, window_seconds=None):
        seen.append((key, max_requests, window_seconds))
        return fake_check.allow

    fake_check.allow = True
    monkeypatch.setattr(public_limits, "check_rate_limit", fake_check)
    monkeypatch.setattr(public_limits.settings, "RATE_LIMIT_ENABLED", True)
    return fake_check, seen


@pytest.mark.asyncio
async def test_allowed_request_passes_and_counts_by_group_and_ip(calls):
    fake, seen = calls
    req = _request(path="/auth/forgot-password", headers={"X-Real-IP": "203.0.113.7"})
    assert await public_limits.enforce_public_limits(req, "/auth/forgot-password") is None
    assert seen == [("rl:send_code:203.0.113.7", 5, 600)]


@pytest.mark.asyncio
async def test_endpoints_in_one_group_share_one_counter(calls):
    _, seen = calls
    ip = {"X-Real-IP": "203.0.113.7"}
    await public_limits.enforce_public_limits(_request(path="/auth/forgot-password", headers=ip), "/auth/forgot-password")
    await public_limits.enforce_public_limits(_request(path="/auth/resend-otp", headers=ip), "/auth/resend-otp")
    assert seen[0][0] == seen[1][0]


@pytest.mark.asyncio
async def test_over_limit_returns_429_with_retry_after(calls):
    fake, _ = calls
    fake.allow = False
    resp = await public_limits.enforce_public_limits(_request(), "/auth/login")
    assert resp.status_code == 429
    assert resp.headers["retry-after"] == "300"
    assert b"RATE_LIMITED" in resp.body


@pytest.mark.asyncio
async def test_unlimited_path_never_touches_redis(calls):
    _, seen = calls
    req = _request(path="/auth/refresh")
    assert await public_limits.enforce_public_limits(req, "/auth/refresh") is None
    assert seen == []


@pytest.mark.asyncio
async def test_switch_turns_limits_off(calls, monkeypatch):
    fake, seen = calls
    fake.allow = False
    monkeypatch.setattr(public_limits.settings, "RATE_LIMIT_ENABLED", False)
    assert await public_limits.enforce_public_limits(_request(), "/auth/login") is None
    assert seen == []


@pytest.mark.asyncio
async def test_real_limiter_fails_open_when_redis_is_down(monkeypatch):
    # No fake here: the real check_rate_limit with an unreachable Redis.
    from app.middleware import rate_limiter

    async def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr(rate_limiter, "get_redis", broken)
    monkeypatch.setattr(public_limits.settings, "RATE_LIMIT_ENABLED", True)
    assert await public_limits.enforce_public_limits(_request(), "/auth/login") is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("*", ["*"]),
        ("", ["*"]),
        ("https://a.example", ["https://a.example"]),
        (
            " https://a.example/ , https://b.example ,",
            ["https://a.example", "https://b.example"],
        ),
    ],
)
def test_cors_origin_list(raw, expected):
    s = GatewaySettings(CORS_ORIGINS=raw, JWT_SECRET_KEY="x")
    assert s.cors_origin_list == expected
