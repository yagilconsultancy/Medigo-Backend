"""New admins get a unique random one-time password, never a shared default."""

import string

from app.config import settings
from app.services.admin_invitation_service import generate_temporary_password


def test_no_shared_default_admin_password_in_settings():
    assert not hasattr(settings, "DEFAULT_ADMIN_PASSWORD")


def test_passwords_are_unique():
    seen = {generate_temporary_password() for _ in range(200)}
    assert len(seen) == 200


def test_password_meets_strict_policy():
    for _ in range(200):
        pw = generate_temporary_password()
        assert len(pw) >= 12
        assert any(c in string.ascii_uppercase for c in pw)
        assert any(c in string.ascii_lowercase for c in pw)
        assert any(c in string.digits for c in pw)
        assert any(c in string.punctuation for c in pw)


def test_old_default_is_never_generated():
    for _ in range(200):
        assert generate_temporary_password() != "MediAdmin2026!"
