#!/bin/bash
set -euo pipefail

# ===========================================
# Initialize MediRide databases on RDS
# ===========================================
# Run this from the EC2 instance after RDS is up
#
# Prerequisites:
#   - postgresql16 client installed (sudo dnf install -y postgresql16)
#   - .env file exists with RDS_HOST, RDS_USERNAME, RDS_PASSWORD
#
# Usage: bash deploy/init-databases-rds.sh

# Load env vars from .env
if [ -f .env ]; then
    export $(grep -E '^(RDS_HOST|RDS_PORT|RDS_USERNAME|RDS_PASSWORD)=' .env | xargs)
fi

RDS_HOST="${RDS_HOST:?ERROR: RDS_HOST not set. Check your .env file.}"
RDS_PORT="${RDS_PORT:-5432}"
RDS_USERNAME="${RDS_USERNAME:?ERROR: RDS_USERNAME not set. Check your .env file.}"
RDS_PASSWORD="${RDS_PASSWORD:?ERROR: RDS_PASSWORD not set. Check your .env file.}"

export PGPASSWORD="$RDS_PASSWORD"

echo "=========================================="
echo "  MediRide RDS Database Initialization"
echo "=========================================="
echo "  Host: $RDS_HOST"
echo "  User: $RDS_USERNAME"
echo ""

# --- Create databases ---
DATABASES=("mediride_users" "mediride_rides" "mediride_locations" "mediride_payments" "mediride_tracking" "mediride_notifications")

for DB in "${DATABASES[@]}"; do
    echo -n "  Creating $DB... "
    psql -h "$RDS_HOST" -p "$RDS_PORT" -U "$RDS_USERNAME" -d mediride_auth -tc \
        "SELECT 1 FROM pg_database WHERE datname = '$DB'" | grep -q 1 && {
        echo "already exists"
    } || {
        psql -h "$RDS_HOST" -p "$RDS_PORT" -U "$RDS_USERNAME" -d mediride_auth -c \
            "CREATE DATABASE $DB;"
        echo "created"
    }
done

# --- Enable PostGIS extensions ---
echo ""
echo "  Enabling PostGIS extensions..."

for DB in "mediride_locations" "mediride_tracking"; do
    echo -n "  PostGIS on $DB... "
    psql -h "$RDS_HOST" -p "$RDS_PORT" -U "$RDS_USERNAME" -d "$DB" -c \
        "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null
    echo "done"
done

echo ""
echo "=========================================="
echo "  All databases ready!"
echo "=========================================="
echo ""
echo "  Databases:"
psql -h "$RDS_HOST" -p "$RDS_PORT" -U "$RDS_USERNAME" -d mediride_auth -tc \
    "SELECT datname FROM pg_database WHERE datname LIKE 'mediride_%' ORDER BY datname;"
echo ""

unset PGPASSWORD
