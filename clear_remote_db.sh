#!/bin/bash

# Clear driver and rider accounts from EC2 staging database

echo "=========================================="
echo "Clearing Driver & Rider Accounts on EC2"
echo "=========================================="

ssh -i ~/Downloads/medi-dev-server.pem ec2-user@ec2-16-58-92-240.us-east-2.compute.amazonaws.com << 'ENDSSH'

echo "Step 1: Clearing data from mediride_users database..."
docker exec -i deploy-postgres-1 psql -U mediride -d mediride_users << 'EOF'
BEGIN;

-- Delete driver suspension logs
DELETE FROM driver_suspension_logs;

-- Delete driver documents
DELETE FROM driver_documents WHERE user_id IN (SELECT user_id FROM driver_profiles);

-- Delete driver invitations
DELETE FROM driver_invitations;

-- Delete fleet applications
DELETE FROM fleet_applications;

-- Delete vehicle maintenance logs
DELETE FROM vehicle_maintenance_logs;

-- Delete vehicle documents
DELETE FROM vehicle_documents;

-- Delete vehicles
DELETE FROM vehicles;

-- Delete driver profiles
DELETE FROM driver_profiles;

-- Delete rider issue notes
DELETE FROM rider_issue_notes;

-- Delete rider issues
DELETE FROM rider_issues;

-- Delete caregiver profiles
DELETE FROM caregiver_profiles;

-- Delete emergency contacts for riders
DELETE FROM emergency_contacts WHERE user_id IN (SELECT id FROM users WHERE role IN ('rider', 'caregiver'));

-- Delete passengers
DELETE FROM passengers;

-- Delete saved locations for riders/drivers/caregivers
DELETE FROM saved_locations WHERE user_id IN (SELECT id FROM users WHERE role IN ('rider', 'driver', 'caregiver'));

-- Delete user settings
DELETE FROM user_settings WHERE user_id IN (SELECT id FROM users WHERE role IN ('driver', 'rider', 'caregiver'));

-- Delete admin role assignments for drivers/riders/caregivers
DELETE FROM admin_role_assignments WHERE user_id IN (SELECT id FROM users WHERE role IN ('driver', 'rider', 'caregiver'));

-- Delete user records (must be last due to foreign keys)
DELETE FROM users WHERE role IN ('driver', 'rider', 'caregiver');

COMMIT;

-- Show remaining users
\echo '--- Remaining Users ---'
SELECT role, COUNT(*) as count FROM users GROUP BY role ORDER BY role;
EOF

echo ""
echo "Step 2: Clearing auth data from mediride_auth database..."
docker exec -i deploy-postgres-1 psql -U mediride -d mediride_auth << 'EOF'
BEGIN;

-- Delete refresh tokens
DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));

-- Delete OTP records
DELETE FROM otp_records WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));

-- Delete password reset tokens
DELETE FROM password_reset_tokens WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));

-- Delete user sessions
DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));

-- Delete login records
DELETE FROM login_records WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));

-- Delete user credentials (must be last)
DELETE FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver');

COMMIT;

-- Show remaining user credentials
\echo '--- Remaining User Credentials ---'
SELECT role, COUNT(*) as count FROM user_credentials GROUP BY role ORDER BY role;
EOF

echo ""
echo "=========================================="
echo "✓ Deletion Complete!"
echo "=========================================="

ENDSSH
