"""
Seed script for development/testing.

Creates a couple of sample bookings (rides) so the dispatch board, rider
history and admin views have data to show immediately.

Usage:
    docker compose exec ride-service python -m scripts.seed_data
    # or
    make seed-rides

The rides are attached to a rider. By default the script looks up the seeded
``rider@test.com`` account in the auth database to reuse its id; you can override
with an explicit id:

    SEED_RIDER_ID=<uuid> docker compose exec ride-service python -m scripts.seed_data
"""

import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.ride import Ride
from mediride_common.database.base import Base
from mediride_common.schemas.enums import (
    RideStatus,
    RideType,
    TripStructure,
    TripType,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://mediride:dev_password@postgres-rides:5432/mediride_rides",
)

# Used only to resolve the seeded rider id when SEED_RIDER_ID is not provided.
AUTH_DATABASE_URL = os.environ.get(
    "AUTH_DATABASE_URL",
    "postgresql+asyncpg://mediride:dev_password@postgres-auth:5432/mediride_auth",
)

SEED_RIDER_EMAIL = os.environ.get("SEED_RIDER_EMAIL", "rider@test.com")

# Fallback if neither SEED_RIDER_ID nor the auth lookup yields a rider.
FALLBACK_RIDER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")

_now = datetime.now(timezone.utc)

# Each entry is a distinct booking. A unique key (used for idempotency) keeps
# re-runs from creating duplicates.
SEED_RIDES = [
    {
        "key": "seed-ride-1",
        "ride_type": RideType.AMBULATORY,
        "trip_type": TripType.TRANSPORT_ONLY,
        "trip_structure": TripStructure.ONE_WAY,
        "status": RideStatus.PENDING,
        "pickup_address": "123 King St W, Toronto, ON",
        "pickup_latitude": 43.6481,
        "pickup_longitude": -79.3845,
        "destination_address": "Toronto General Hospital, 200 Elizabeth St, Toronto, ON",
        "destination_latitude": 43.6590,
        "destination_longitude": -79.3886,
        "scheduled_at": _now + timedelta(hours=2),
        "visit_type": "checkup",
        "facility_name": "Toronto General Hospital",
        "passenger_first_name": "Test",
        "passenger_last_name": "Rider",
        "passenger_phone": "+14165550101",
        "estimated_distance_miles": 1.4,
        "estimated_duration_minutes": 12,
        "estimated_fare": 24.50,
    },
    {
        "key": "seed-ride-2",
        "ride_type": RideType.WHEELCHAIR,
        "trip_type": TripType.TRANSPORT_CARE_ASSISTANT,
        "trip_structure": TripStructure.ROUND_TRIP,
        "status": RideStatus.CONFIRMED,
        "pickup_address": "55 Bloor St E, Toronto, ON",
        "pickup_latitude": 43.6710,
        "pickup_longitude": -79.3860,
        "destination_address": "Sunnybrook Health Sciences Centre, 2075 Bayview Ave, Toronto, ON",
        "destination_latitude": 43.7227,
        "destination_longitude": -79.3742,
        "scheduled_at": _now + timedelta(days=1, hours=3),
        "visit_type": "therapy",
        "facility_name": "Sunnybrook Health Sciences Centre",
        "passenger_first_name": "Test",
        "passenger_last_name": "Rider",
        "passenger_phone": "+14165550101",
        "mobility_level": "wheelchair",
        "estimated_distance_miles": 5.2,
        "estimated_duration_minutes": 22,
        "estimated_fare": 58.00,
    },
]


async def resolve_rider_id() -> uuid.UUID:
    """Pick the rider these bookings belong to."""
    override = os.environ.get("SEED_RIDER_ID")
    if override:
        logger.info("Using rider id from SEED_RIDER_ID: %s", override)
        return uuid.UUID(override)

    # Best-effort lookup of the seeded rider in the auth database.
    try:
        engine = create_async_engine(AUTH_DATABASE_URL)
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text

                result = await conn.execute(
                    text("SELECT id FROM user_credentials WHERE email = :email"),
                    {"email": SEED_RIDER_EMAIL},
                )
                row = result.first()
        finally:
            await engine.dispose()
        if row:
            logger.info(
                "Resolved rider id for %s: %s", SEED_RIDER_EMAIL, row[0]
            )
            return row[0]
        logger.warning(
            "Rider %s not found in auth db; run `make seed` first.",
            SEED_RIDER_EMAIL,
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Could not look up rider in auth db: %s", exc)

    logger.info("Falling back to rider id %s", FALLBACK_RIDER_ID)
    return FALLBACK_RIDER_ID


async def seed():
    rider_id = await resolve_rider_id()

    engine = create_async_engine(DATABASE_URL)

    # Ensure tables exist (in case migrations have not been run).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        for ride_data in SEED_RIDES:
            key = ride_data["key"]
            instructions = f"[{key}] Seeded booking"

            # Idempotency: skip if a ride with this marker already exists.
            existing = await session.execute(
                select(Ride).where(Ride.special_instructions == instructions)
            )
            if existing.scalar_one_or_none():
                logger.info("  [SKIP] %s - already exists", key)
                continue

            fields = {k: v for k, v in ride_data.items() if k != "key"}
            ride = Ride(
                rider_id=rider_id,
                special_instructions=instructions,
                booking_channel="seed",
                **fields,
            )
            session.add(ride)
            await session.flush()
            logger.info(
                "  [CREATED] %s - id: %s (%s)",
                key,
                ride.id,
                ride.status,
            )

        await session.commit()

    await engine.dispose()

    print("\n" + "=" * 60)
    print("  RIDE SEED DATA COMPLETE")
    print("=" * 60)
    print(f"  Rider id: {rider_id}")
    print(f"  Bookings seeded: {len(SEED_RIDES)}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    if os.environ.get("ENVIRONMENT", "development") != "development":
        sys.exit("Seed data is for local development only.")
    asyncio.run(seed())
