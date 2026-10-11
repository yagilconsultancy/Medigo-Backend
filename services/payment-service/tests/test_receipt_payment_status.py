import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

sys.path.append(str(Path(__file__).resolve().parents[3] / "libs" / "common"))

from app.services.receipt_service import ReceiptService


class _Repo:
    async def get_by_ride_id(self, ride_id):
        return None

    async def get_by_user(self, user_id):
        return []


class _RideClient:
    def __init__(self, ride):
        self.ride = ride

    async def get_ride(self, ride_id):
        return self.ride


class _TxRepo:
    def __init__(self, txs):
        self.txs = txs

    async def get_by_ride_id(self, ride_id):
        return self.txs


def _tx(kind, status):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        transaction_type=kind, status=status, created_at=now, updated_at=now
    )


async def _receipt(txs, viewer="rider"):
    rider, driver = uuid4(), uuid4()
    ride = {
        "rider_id": str(rider),
        "driver_id": str(driver),
        "status": "completed",
        "final_fare": 30,
    }
    service = ReceiptService(
        fare_repo=_Repo(),
        pm_repo=_Repo(),
        ride_client=_RideClient(ride),
        tx_repo=_TxRepo(txs),
    )
    return await service.generate_receipt(uuid4(), rider if viewer == "rider" else driver)


@pytest.mark.anyio
async def test_no_transactions_is_not_recorded():
    r = await _receipt([])
    assert r["payment_status"] == "not_recorded"
    assert r["paid_at"] is None


@pytest.mark.anyio
async def test_completed_payment_is_paid_with_time():
    r = await _receipt([_tx("ride_payment", "completed")])
    assert r["payment_status"] == "paid"
    assert r["paid_at"]


@pytest.mark.anyio
async def test_pending_payment_is_pending():
    r = await _receipt([_tx("ride_payment", "pending")])
    assert r["payment_status"] == "pending"


@pytest.mark.anyio
async def test_failed_payment_is_failed():
    r = await _receipt([_tx("ride_payment", "failed")])
    assert r["payment_status"] == "failed"


@pytest.mark.anyio
async def test_refunded_payment_is_refunded():
    r = await _receipt(
        [_tx("ride_payment", "completed"), _tx("refund", "completed")]
    )
    assert r["payment_status"] == "refunded"


@pytest.mark.anyio
async def test_driver_never_sees_payment_state():
    r = await _receipt([_tx("ride_payment", "completed")], viewer="driver")
    assert r["payment_status"] == "not_recorded"
    assert r["paid_at"] is None
