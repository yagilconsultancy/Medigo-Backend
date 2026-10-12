"""Tests for the shared secret used on service-to-service (/internal) calls."""
import logging
import re
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mediride_common.auth.internal import (
    DEV_INTERNAL_TOKEN,
    INTERNAL_SERVICE_HEADER,
    INTERNAL_TOKEN_HEADER,
    internal_headers,
    require_internal_service,
)

REAL_TOKEN = "unit-test-secret-value"
REPO_ROOT = Path(__file__).resolve().parents[3]


def make_client() -> TestClient:
    app = FastAPI()

    @app.get("/internal/ping")
    async def ping(caller: str = Depends(require_internal_service)):
        return {"caller": caller}

    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_MODE", raising=False)
    monkeypatch.delenv("INTERNAL_SERVICE_TOKEN", raising=False)


def test_helper_sends_name_and_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", REAL_TOKEN)
    assert internal_headers("ride-service") == {
        INTERNAL_SERVICE_HEADER: "ride-service",
        INTERNAL_TOKEN_HEADER: REAL_TOKEN,
    }


def test_helper_accepts_explicit_token():
    assert internal_headers("x", "abc")[INTERNAL_TOKEN_HEADER] == "abc"


def test_no_caller_name_is_always_refused(monkeypatch):
    for mode in ("off", "log", "enforce"):
        monkeypatch.setenv("INTERNAL_AUTH_MODE", mode)
        assert make_client().get("/internal/ping").status_code == 403


def test_default_mode_is_log_and_allows_but_warns(caplog):
    with caplog.at_level(logging.WARNING):
        r = make_client().get("/internal/ping", headers={INTERNAL_SERVICE_HEADER: "old-caller"})
    assert r.status_code == 200
    assert "INTERNAL_CALL_WITHOUT_VALID_TOKEN" in caplog.text
    assert "old-caller" in caplog.text
    assert "/internal/ping" in caplog.text


def test_log_mode_no_warning_with_valid_token(monkeypatch, caplog):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", REAL_TOKEN)
    with caplog.at_level(logging.WARNING):
        r = make_client().get("/internal/ping", headers=internal_headers("ride-service"))
    assert r.status_code == 200
    assert r.json() == {"caller": "ride-service"}
    assert "INTERNAL_CALL_WITHOUT_VALID_TOKEN" not in caplog.text


def test_enforce_blocks_missing_and_wrong_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_MODE", "enforce")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", REAL_TOKEN)
    client = make_client()
    assert client.get("/internal/ping", headers={INTERNAL_SERVICE_HEADER: "x"}).status_code == 403
    wrong = {INTERNAL_SERVICE_HEADER: "x", INTERNAL_TOKEN_HEADER: "nope"}
    assert client.get("/internal/ping", headers=wrong).status_code == 403


def test_enforce_allows_right_token(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_MODE", "enforce")
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", REAL_TOKEN)
    r = make_client().get("/internal/ping", headers=internal_headers("payment-service"))
    assert r.status_code == 200


def test_enforce_refuses_built_in_development_secret(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_MODE", "enforce")
    # token unset -> the development default is both sent and expected
    r = make_client().get("/internal/ping", headers=internal_headers("payment-service"))
    assert r.status_code == 403
    assert DEV_INTERNAL_TOKEN == internal_headers("a")[INTERNAL_TOKEN_HEADER]


def test_off_mode_keeps_old_behaviour(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_MODE", "off")
    r = make_client().get("/internal/ping", headers={INTERNAL_SERVICE_HEADER: "x"})
    assert r.status_code == 200


def test_unknown_mode_falls_back_to_log(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_MODE", "banana")
    r = make_client().get("/internal/ping", headers={INTERNAL_SERVICE_HEADER: "x"})
    assert r.status_code == 200


def test_no_service_still_builds_its_own_internal_headers():
    """Guard: every service-to-service call must use internal_headers(...).

    A hand-written {"X-Internal-Service": "..."} dict would skip the secret and
    show up as a warning (or a 403 once enforcement is on).
    """
    offenders = []
    for path in list((REPO_ROOT / "services").rglob("*.py")) + list((REPO_ROOT / "libs").rglob("*.py")):
        if "tests" in path.parts or path.name == "internal.py":
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"""["']X-Internal-Service["']\s*:""", text):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_every_internal_route_file_uses_the_shared_check():
    for path in (REPO_ROOT / "services").glob("*/app/api/v1/internal_endpoints.py"):
        text = path.read_text(encoding="utf-8")
        assert "mediride_common.auth.internal import require_internal_service" in text, path
        assert "x_internal_service" not in text, path
