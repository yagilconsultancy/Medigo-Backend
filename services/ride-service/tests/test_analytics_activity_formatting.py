from app.services.analytics_service import (
    _format_activity_notes,
    _format_status_label,
)


def test_format_status_label_title_cases_snake_case_status():
    assert _format_status_label("driver_assigned") == "Driver Assigned"


def test_format_activity_notes_replaces_driver_uuid_with_name():
    notes = "Admin assigned driver e1c7e879-7575-4c5f-8f83-3fa7a2ff9d20"

    formatted = _format_activity_notes(
        notes,
        {"e1c7e879-7575-4c5f-8f83-3fa7a2ff9d20": "Ada Lovelace"},
    )

    assert formatted == "Assigned to Ada Lovelace"


def test_format_activity_notes_formats_reassignment_names():
    notes = "Driver reassigned: Grace Hopper → Katherine Johnson"

    formatted = _format_activity_notes(notes, {})

    assert formatted == "Driver reassigned: Grace Hopper to Katherine Johnson"
