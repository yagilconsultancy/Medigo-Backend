#!/bin/bash

# Clear old driver and rider accounts from development database

echo "=========================================="
echo "Clearing Driver and Rider Accounts"
echo "=========================================="

# Execute the SQL script
docker exec -i infra-postgres-1 psql -U mediride -d mediride << 'EOF'
BEGIN;

-- Delete driver-related data
DELETE FROM driver_suspension_logs WHERE driver_id IN (SELECT user_id FROM driver_profiles);
DELETE FROM driver_documents WHERE driver_id IN (SELECT user_id FROM driver_profiles);
DELETE FROM driver_invitations;
DELETE FROM fleet_applications WHERE driver_id IN (SELECT user_id FROM driver_profiles);
DELETE FROM fleet_drivers WHERE driver_id IN (SELECT user_id FROM driver_profiles);
DELETE FROM vehicle_maintenance_logs WHERE vehicle_id IN (SELECT id FROM vehicles WHERE driver_id IN (SELECT user_id FROM driver_profiles));
DELETE FROM vehicle_documents WHERE vehicle_id IN (SELECT id FROM vehicles WHERE driver_id IN (SELECT user_id FROM driver_profiles));
DELETE FROM vehicles WHERE driver_id IN (SELECT user_id FROM driver_profiles);
DELETE FROM driver_profiles;

-- Delete rider-related data
DELETE FROM rider_issue_notes WHERE issue_id IN (SELECT id FROM rider_issues);
DELETE FROM rider_issues;
DELETE FROM emergency_contacts WHERE user_id IN (SELECT id FROM users WHERE role = 'rider');
DELETE FROM passengers;
DELETE FROM saved_locations WHERE user_id IN (SELECT id FROM users WHERE role IN ('rider', 'driver', 'caregiver'));

-- Delete caregiver data
DELETE FROM caregiver_profiles;

-- Delete user settings
DELETE FROM user_settings WHERE user_id IN (SELECT id FROM users WHERE role IN ('driver', 'rider', 'caregiver'));

-- Delete auth service data
DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));
DELETE FROM otp_records WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));
DELETE FROM password_reset_tokens WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));
DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));
DELETE FROM login_records WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));
DELETE FROM activity_logs WHERE user_id IN (SELECT id FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver'));
DELETE FROM user_credentials WHERE role IN ('driver', 'rider', 'caregiver');

-- Delete user records (must be last)
DELETE FROM users WHERE role IN ('driver', 'rider', 'caregiver');

COMMIT;

-- Show remaining accounts
SELECT role, COUNT(*) as count FROM users GROUP BY role ORDER BY role;
EOF

echo ""
echo "=========================================="
echo "Deletion Complete!"
echo "=========================================="
