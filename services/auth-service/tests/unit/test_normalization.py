from app.normalization import normalize_email, normalize_phone


def test_normalize_email_lowercases_and_strips():
    assert normalize_email("  Moses.OladunjoyeJobs@Gmail.com  ") == "moses.oladunjoyejobs@gmail.com"


def test_normalize_email_returns_none_for_blank():
    assert normalize_email("   ") is None


def test_normalize_phone_strips_whitespace():
    assert normalize_phone("  +14165550123  ") == "+14165550123"


def test_normalize_phone_returns_none_for_blank():
    assert normalize_phone("   ") is None
