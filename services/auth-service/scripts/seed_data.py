"""
Seed script for development/testing.

Creates test users with pre-verified accounts so you can log in immediately.
All users use password: Test1234

Usage:
    docker compose exec auth-service python -m scripts.seed_data
    # or
    make seed

Test Accounts:
    - rider@test.com      (rider)       password: Test1234
    - driver@test.com     (driver)      password: Test1234
    - admin@test.com      (admin)       password: Test1234
    - business@test.com   (business)    password: Test1234

OTP for all accounts: 123456
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.user_credential import UserCredential
from app.services.password_service import hash_password
from mediride_common.database.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://mediride:dev_password@postgres-auth:5432/mediride_auth",
)

DEFAULT_PASSWORD = "Test1234"

SEED_USERS = [
    {
        "email": "rider@test.com",
        "phone": "+1234567001",
        "role": "rider",
    },
    {
        "email": "driver@test.com",
        "phone": "+1234567002",
        "role": "driver",
    },
    {
        "email": "admin@test.com",
        "phone": "+1234567003",
        "role": "admin",
    },
    {
        "email": "business@test.com",
        "phone": "+1234567004",
        "role": "business",
    },
]


async def seed():
    engine = create_async_engine(DATABASE_URL)

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    password_hash = hash_password(DEFAULT_PASSWORD)

    async with session_factory() as session:
        for user_data in SEED_USERS:
            # Check if user already exists
            result = await session.execute(
                select(UserCredential).where(
                    UserCredential.email == user_data["email"]
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(f"  [SKIP] {user_data['email']} ({user_data['role']}) - already exists")
                continue

            credential = UserCredential(
                email=user_data["email"],
                phone=user_data["phone"],
                password_hash=password_hash,
                role=user_data["role"],
                is_verified=True,
                is_active=True,
            )
            session.add(credential)
            await session.flush()
            logger.info(f"  [CREATED] {user_data['email']} ({user_data['role']}) - id: {credential.id}")

        await session.commit()

    await engine.dispose()

    print("\n" + "=" * 60)
    print("  SEED DATA COMPLETE")
    print("=" * 60)
    print(f"  Password for all accounts: {DEFAULT_PASSWORD}")
    print(f"  OTP for verification:      123456")
    print()
    print("  Test Accounts:")
    for user_data in SEED_USERS:
        print(f"    {user_data['email']:25s} role: {user_data['role']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed())
