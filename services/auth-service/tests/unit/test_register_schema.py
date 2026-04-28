from app.schemas.auth import RegisterRequest


def test_register_request_splits_full_name_into_first_and_last_name():
    request = RegisterRequest(
        email="sarah@example.com",
        password="StrongPass123!",
        full_name="Sarah Johnson",
    )

    assert request.first_name == "Sarah"
    assert request.last_name == "Johnson"


def test_register_request_allows_single_word_full_name():
    request = RegisterRequest(
        phone="+14165550123",
        password="StrongPass123!",
        full_name="Prince",
    )

    assert request.first_name == "Prince"
    assert request.last_name == ""
