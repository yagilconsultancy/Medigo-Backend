from pathlib import Path
from uuid import UUID, uuid4
import sys

sys.path.append(str(Path(__file__).resolve().parents[3] / "libs" / "common"))

from app.services.admin_transaction_service import _booking_ref


def test_booking_ref_is_derived_from_the_ride_id():
    ride_id = UUID("3f2a9c41-1234-4c5d-8e9f-0123456789ab")

    assert _booking_ref(ride_id) == "BK-3F2A9C41"


def test_booking_ref_is_stable_for_the_same_ride():
    ride_id = uuid4()

    assert _booking_ref(ride_id) == _booking_ref(str(ride_id))


def test_booking_ref_matches_the_format_used_by_the_other_services():
    # ride-service dispatch and notification-service emails both build the ref
    # as BK-<first 8 chars of the ride id, uppercased>; admins compare them.
    ride_id = uuid4()

    assert _booking_ref(ride_id) == f"BK-{str(ride_id)[:8].upper()}"


def test_booking_ref_is_none_without_a_ride():
    assert _booking_ref(None) is None
