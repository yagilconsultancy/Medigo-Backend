def normalize_email(email: str | None) -> str | None:
    if email is None:
        return None

    normalized = email.strip().lower()
    return normalized or None


def normalize_phone(phone: str | None) -> str | None:
    if phone is None:
        return None

    normalized = phone.strip()
    return normalized or None
