-- =====================================================
-- MEDIRIDE: Clear Old Driver and Rider Accounts
-- =====================================================
-- This script deletes all driver and rider accounts while preserving:
-- - Admin accounts
-- - Business accounts
-- - System data
--
-- IMPORTANT: This will permanently delete data. Make a backup first!
-- Run: docker exec deploy-postgres-1 pg_dump -U mediride mediride > backup_$(date +%Y%m%d_%H%M%S).sql
-- =====================================================

BEGIN;

-- =====================================================
-- STEP 1: Delete Driver-Related Data
-- =====================================================

-- Delete driver suspension logs
DELETE FROM driver_suspension_logs
WHERE driver_id IN (
    SELECT user_id FROM driver_profiles
);

-- Delete driver documents
DELETE FROM driver_documents
WHERE driver_id IN (
    SELECT user_id FROM driver_profiles
);

-- Delete driver invitations
DELETE FROM driver_invitations;

-- Delete fleet applications (if drivers applied to fleets)
DELETE FROM fleet_applications
WHERE driver_id IN (
    SELECT user_id FROM driver_profiles
);

-- Delete fleet associations
DELETE FROM fleet_drivers
WHERE driver_id IN (
    SELECT user_id FROM driver_profiles
);

-- Delete vehicle maintenance logs
DELETE FROM vehicle_maintenance_logs
WHERE vehicle_id IN (
    SELECT id FROM vehicles
    WHERE driver_id IN (SELECT user_id FROM driver_profiles)
);

-- Delete vehicle documents
DELETE FROM vehicle_documents
WHERE vehicle_id IN (
    SELECT id FROM vehicles
    WHERE driver_id IN (SELECT user_id FROM driver_profiles)
);

-- Delete vehicles owned by drivers
DELETE FROM vehicles
WHERE driver_id IN (
    SELECT user_id FROM driver_profiles
);

-- Delete driver profiles
DELETE FROM driver_profiles;

-- =====================================================
-- STEP 2: Delete Rider-Related Data
-- =====================================================

-- Delete rider issue notes
DELETE FROM rider_issue_notes
WHERE issue_id IN (
    SELECT id FROM rider_issues
);

-- Delete rider issues
DELETE FROM rider_issues;

-- Delete emergency contacts for riders
DELETE FROM emergency_contacts
WHERE user_id IN (
    SELECT id FROM users WHERE role = 'rider'
);

-- Delete passengers (dependents)
DELETE FROM passengers;

-- Delete saved locations for riders
DELETE FROM saved_locations
WHERE user_id IN (
    SELECT id FROM users WHERE role = 'rider'
);

-- =====================================================
-- STEP 3: Delete Caregiver Data (if applicable)
-- =====================================================

-- Delete caregiver profiles
DELETE FROM caregiver_profiles;

-- Delete saved locations for caregivers
DELETE FROM saved_locations
WHERE user_id IN (
    SELECT id FROM users WHERE role = 'caregiver'
);

-- =====================================================
-- STEP 4: Delete User Settings for Drivers/Riders/Caregivers
-- =====================================================

DELETE FROM user_settings
WHERE user_id IN (
    SELECT id FROM users
    WHERE role IN ('driver', 'rider', 'caregiver')
);

-- =====================================================
-- STEP 5: Delete Auth Service Data
-- =====================================================

-- Delete refresh tokens for drivers/riders/caregivers
DELETE FROM refresh_tokens
WHERE user_id IN (
    SELECT id FROM user_credentials
    WHERE role IN ('driver', 'rider', 'caregiver')
);

-- Delete OTP records for drivers/riders/caregivers
DELETE FROM otp_records
WHERE user_id IN (
    SELECT id FROM user_credentials
    WHERE role IN ('driver', 'rider', 'caregiver')
);

-- Delete password reset tokens for drivers/riders/caregivers
DELETE FROM password_reset_tokens
WHERE user_id IN (
    SELECT id FROM user_credentials
    WHERE role IN ('driver', 'rider', 'caregiver')
);

-- Delete user sessions for drivers/riders/caregivers
DELETE FROM user_sessions
WHERE user_id IN (
    SELECT id FROM user_credentials
    WHERE role IN ('driver', 'rider', 'caregiver')
);

-- Delete login records for drivers/riders/caregivers
DELETE FROM login_records
WHERE user_id IN (
    SELECT id FROM user_credentials
    WHERE role IN ('driver', 'rider', 'caregiver')
);

-- Delete activity logs for drivers/riders/caregivers
DELETE FROM activity_logs
WHERE user_id IN (
    SELECT id FROM user_credentials
    WHERE role IN ('driver', 'rider', 'caregiver')
);

-- Delete user credentials for drivers/riders/caregivers
DELETE FROM user_credentials
WHERE role IN ('driver', 'rider', 'caregiver');

-- =====================================================
-- STEP 6: Delete User Records (Final Step)
-- =====================================================

-- Delete user records for drivers, riders, and caregivers
-- This must be last due to foreign key constraints
DELETE FROM users
WHERE role IN ('driver', 'rider', 'caregiver');

-- =====================================================
-- STEP 7: Verify Deletion and Show Remaining Accounts
-- =====================================================

-- Show remaining users (should only be admins and business users)
SELECT
    role,
    COUNT(*) as count
FROM users
GROUP BY role
ORDER BY role;

-- Show remaining user credentials (should only be admins and business users)
SELECT
    role,
    COUNT(*) as count
FROM user_credentials
GROUP BY role
ORDER BY role;

COMMIT;

-- =====================================================
-- ROLLBACK OPTION
-- =====================================================
-- If you want to undo these changes before COMMIT, run:
-- ROLLBACK;
-- =====================================================
