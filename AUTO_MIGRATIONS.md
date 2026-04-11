# Auto-Migration Setup

All MediRide services now automatically run database migrations on startup using entrypoint scripts.

## How It Works

Each service with a database has:
1. **entrypoint.sh** - Bash script that runs migrations before starting the service
2. **Updated Dockerfile** - Copies entrypoint script and uses it as the CMD

### Entrypoint Script Flow

```bash
#!/bin/bash
set -e  # Exit on error

echo "Running database migrations..."
alembic upgrade head  # Apply all pending migrations

echo "Starting [service-name]..."
exec uvicorn app.main:app --host 0.0.0.0 --port [PORT] --workers [N]
```

## Services with Auto-Migration

All 7 microservices now auto-migrate on startup:

| Service | Port | Migrations | App Type |
|---------|------|------------|----------|
| auth-service | 8001 | 5 | app |
| user-service | 8002 | 16 | app |
| ride-service | 8003 | 11 | app |
| location-service | 8004 | 2 | app |
| payment-service | 8005 | 10 | app |
| tracking-service | 8006 | 1 | socket_app |
| notification-service | 8007 | 6 | socket_app |

## Usage

### Starting Services

```bash
# Rebuild and start all services (migrations run automatically)
docker-compose up -d --build

# Check migration logs
docker-compose logs user-service | grep "Running database migrations"
docker-compose logs location-service | grep "Running database migrations"
```

### Manual Migration (if needed)

If you need to run migrations manually:

```bash
docker exec mediride-user-service-1 alembic upgrade head
docker exec mediride-location-service-1 alembic upgrade head
# etc.
```

### Creating New Migrations

```bash
# Generate a new migration
docker exec mediride-user-service-1 alembic revision --autogenerate -m "description"

# The new migration will auto-apply on next container restart
docker-compose restart user-service
```

## Benefits

✅ **Zero Manual Work** - No need to manually run migrations after deployment
✅ **Consistent State** - Database always matches code on startup
✅ **Fail Fast** - Service won't start if migrations fail
✅ **Production Ready** - Same behavior in dev, staging, and production
✅ **CI/CD Friendly** - Deploys automatically apply schema changes

## Migration Safety

The entrypoint script uses `set -e` which means:
- If migration fails, the service won't start
- Container will exit with error status
- Docker Compose will show the service as unhealthy
- You can check logs to see what went wrong

## Troubleshooting

### Service won't start

```bash
# Check if migration failed
docker-compose logs [service-name]

# Look for errors after "Running database migrations..."
docker-compose logs user-service | grep -A 10 "Running database migrations"
```

### Database locked or stuck

```bash
# Stop all services
docker-compose down

# Start database first, then services
docker-compose up -d postgres-users postgres-locations
sleep 5
docker-compose up -d user-service location-service
```

### Rollback a migration

```bash
# Manually downgrade inside container
docker exec mediride-user-service-1 alembic downgrade -1

# Or stop service, downgrade, restart
docker-compose stop user-service
docker exec mediride-user-service-1 alembic downgrade [revision]
docker-compose start user-service
```

## Files Added

For each service with migrations:

```
services/[service-name]/
├── entrypoint.sh          # NEW - Auto-migration script
├── Dockerfile            # MODIFIED - Added entrypoint
├── alembic/
│   └── versions/         # Migration files
└── alembic.ini           # Alembic config
```

## Example Logs

When a service starts, you'll see:

```
user-service_1      | Running database migrations...
user-service_1      | INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
user-service_1      | INFO  [alembic.runtime.migration] Will assume transactional DDL.
user-service_1      | INFO  [alembic.runtime.migration] Running upgrade 014 -> 015, admin roles and permissions
user-service_1      | Starting user service...
user-service_1      | INFO:     Started server process [1]
user-service_1      | INFO:     Waiting for application startup.
user-service_1      | INFO:     Application startup complete.
```

## Next Deploy

When you deploy new code with migrations:

1. `docker-compose pull` (or build new images)
2. `docker-compose up -d`
3. Services automatically apply pending migrations
4. No manual intervention needed!

---

This setup ensures your database schema is always in sync with your application code, making deployments safer and more predictable.
