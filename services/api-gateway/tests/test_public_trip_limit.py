from app.middleware.public_limits import GROUP_LIMITS, limit_group_for


def test_trip_view_paths_are_limited_per_visitor():
    assert limit_group_for("GET", "/rides/public/track/abc123_-token") == "trip_view"
    assert "trip_view" in GROUP_LIMITS


def test_other_methods_and_paths_are_not_in_the_trip_view_group():
    assert limit_group_for("POST", "/rides/public/track/abc123") is None
    assert limit_group_for("GET", "/rides/public/other") is None
    assert limit_group_for("GET", "/rides/shared/abc123") is None


def test_exact_rules_still_work():
    assert limit_group_for("POST", "/auth/login") == "login"
    assert limit_group_for("post", "/auth/login/") == "login"
