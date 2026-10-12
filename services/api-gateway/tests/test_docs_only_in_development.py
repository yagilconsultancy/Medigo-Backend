import pytest

from app.routes import proxy


@pytest.mark.parametrize(
    "environment,expected",
    [("development", True), ("staging", False), ("production", False)],
)
def test_docs_are_served_only_in_development(monkeypatch, environment, expected):
    monkeypatch.setattr(proxy.settings, "ENVIRONMENT", environment)
    assert proxy._docs_enabled() is expected
    assert proxy._is_public_path("/auth/docs") is expected
