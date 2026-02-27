"""
Seed script for development data.
Run: docker compose exec auth-service python -m scripts.seed_data
"""
import asyncio
import uuid

# This script would be expanded to create:
# 1. Admin user
# 2. Sample business
# 3. Sample driver invitation
# 4. Sample rider account


async def seed():
    print("=== MediRide Seed Data ===")
    print("Seeding would create:")
    print("  - Admin user (admin@mediride.com)")
    print("  - Sample business (Springfield Medical Transport)")
    print("  - Sample driver invitation")
    print("  - Sample rider (rider@example.com)")
    print()
    print("To seed data, use the API endpoints directly:")
    print()
    print("1. Register admin:")
    print('   POST /api/v1/auth/register {"email":"admin@mediride.com","password":"Admin123!","role":"admin"}')
    print()
    print("2. Create business (after admin login):")
    print('   POST /api/v1/users/businesses {"name":"Springfield Medical Transport","type":"hospital"}')
    print()
    print("3. Invite driver:")
    print('   POST /api/v1/users/businesses/{id}/invitations {"email":"driver@example.com"}')
    print()
    print("4. Register rider:")
    print('   POST /api/v1/auth/register {"email":"rider@example.com","password":"Rider123!","role":"rider"}')


if __name__ == "__main__":
    asyncio.run(seed())
