-- Initialize all MediRide databases on a single PostgreSQL instance
-- This runs automatically on first container startup via docker-entrypoint-initdb.d

-- mediride_auth is created by POSTGRES_DB env var, so skip it

CREATE DATABASE mediride_users;
CREATE DATABASE mediride_rides;
CREATE DATABASE mediride_locations;
CREATE DATABASE mediride_payments;
CREATE DATABASE mediride_tracking;
CREATE DATABASE mediride_notifications;

-- Enable PostGIS on databases that need spatial queries
\c mediride_locations
CREATE EXTENSION IF NOT EXISTS postgis;

\c mediride_tracking
CREATE EXTENSION IF NOT EXISTS postgis;
