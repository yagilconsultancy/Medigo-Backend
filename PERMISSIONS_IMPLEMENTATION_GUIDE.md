# Admin Roles & Permissions Implementation Guide

This guide explains how to use the module-based permissions system implemented for MediRide.

## Overview

The system provides **both frontend and backend enforcement** of module permissions:
- **Frontend**: Conditionally renders sidebar menu items based on user's accessible modules
- **Backend**: Middleware validates module access on each API call

## Architecture

```
┌─────────────┐         ┌──────────────────┐         ┌──────────────┐
│   Frontend  │────1───▶│  GET /admin/me/  │         │              │
│             │         │    permissions   │         │              │
└─────────────┘         └──────────────────┘         │              │
       │                         │                   │              │
       │                         ▼                   │              │
       │                ┌─────────────────┐          │ user-service │
       │                │ Accessible      │          │              │
       │                │ Modules:        │          │              │
       │                │ - booking_mgmt  │          │              │
       │                │ - driver_mgmt   │          │              │
       │                │ - fleet_mgmt    │          │              │
       └──Hide/Show────▶│ etc.            │          │              │
          Sidebar       └─────────────────┘          │              │
                                                     │              │
┌─────────────┐         ┌──────────────────┐         │              │
│   API Call  │────2───▶│  Middleware      │────3───▶│ Check DB:    │
│ (with JWT)  │         │  Checks Module   │         │ user_roles   │
└─────────────┘         │  Permission      │         │ + perms      │
       │                └──────────────────┘         └──────────────┘
       │                         │
       │                    ✓ Allowed
       ▼                         │
┌─────────────┐◀────────────────┘
│   Execute   │
│  Endpoint   │
└─────────────┘
```

## 1. Frontend Implementation

### Step 1: Fetch User Permissions on Login

```typescript
// services/auth.ts
export async function getCurrentUserPermissions() {
  const response = await api.get('/users/admin/me/permissions');
  return response.data.data; // { user, roles, accessible_modules }
}
```

### Step 2: Store in Context/Redux

```typescript
// context/PermissionsContext.tsx
interface PermissionsContext {
  user: { id: string; full_name: string; email: string };
  roles: Array<{ id: string; name: string; display_name: string; color: string }>;
  accessible_modules: string[];
  hasModuleAccess: (module: string) => boolean;
}

export const PermissionsProvider = ({ children }) => {
  const [permissions, setPermissions] = useState<PermissionsContext | null>(null);

  useEffect(() => {
    // Fetch on mount
    getCurrentUserPermissions().then(setPermissions);
  }, []);

  const hasModuleAccess = (module: string) => {
    return permissions?.accessible_modules.includes(module) ?? false;
  };

  return (
    <PermissionsContext.Provider value={{ ...permissions, hasModuleAccess }}>
      {children}
    </PermissionsContext.Provider>
  );
};
```

### Step 3: Conditionally Render Sidebar

```typescript
// components/Sidebar.tsx
import { usePermissions } from '@/context/PermissionsContext';

const MENU_ITEMS = [
  { label: 'Dashboard Overview', module: 'analytics_dashboard', icon: '📊' },
  { label: 'Booking Management', module: 'booking_management', icon: '📅' },
  { label: 'Dispatch Center', module: 'dispatch_center', icon: '🚀' },
  { label: 'GPS Tracking', module: 'gps_tracking', icon: '📍' },
  { label: 'Fleet Management', module: 'fleet_management', icon: '🚗' },
  { label: 'Driver Management', module: 'driver_management', icon: '👨‍✈️' },
  { label: 'Vehicle Management', module: 'vehicle_management', icon: '🚙' },
  { label: 'Rider Management', module: 'rider_management', icon: '👥' },
  { label: 'Payments & Finance', module: 'payments_finance', icon: '💰' },
  { label: 'Invoices & Billing', module: 'invoices_billing', icon: '📄' },
  { label: 'Safety & Incidents', module: 'safety_incidents', icon: '⚠️' },
  { label: 'Notifications', module: 'notifications', icon: '🔔' },
  { label: 'Support Center', module: 'support_center', icon: '💬' },
  { label: 'Dashboard Settings', module: 'dashboard_settings', icon: '⚙️', children: [
    { label: 'Cities & Service Area', module: 'dashboard_settings' },
    { label: 'Ride Types', module: 'dashboard_settings' },
    { label: 'Roles & Permissions', module: 'roles_permissions' },
  ]},
  { label: 'System Logs', module: 'system_logs', icon: '📋' },
];

export function Sidebar() {
  const { hasModuleAccess } = usePermissions();

  return (
    <nav>
      {MENU_ITEMS.filter(item => hasModuleAccess(item.module)).map(item => (
        <SidebarItem key={item.module} {...item} />
      ))}
    </nav>
  );
}
```

### Step 4: Protect Routes

```typescript
// components/ProtectedRoute.tsx
import { Navigate } from 'react-router-dom';
import { usePermissions } from '@/context/PermissionsContext';

interface ProtectedRouteProps {
  module: string;
  children: React.ReactNode;
}

export function ProtectedRoute({ module, children }: ProtectedRouteProps) {
  const { hasModuleAccess } = usePermissions();

  if (!hasModuleAccess(module)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}

// Usage in router
<Route
  path="/admin/drivers"
  element={
    <ProtectedRoute module="driver_management">
      <DriverManagementPage />
    </ProtectedRoute>
  }
/>
```

## 2. Backend Implementation

### For User-Service (has admin_roles tables locally)

```python
# app/api/v1/admin_driver_endpoints.py
from mediride_common.auth.permissions import require_module_access
from app.dependencies import get_db

@router.get("/admin/drivers")
async def list_drivers(
    # Replace require_role([UserRole.ADMIN]) with require_module_access
    _admin: UserClaims = Depends(require_module_access("driver_management", get_db)),
    service: AdminDriverService = Depends(_get_service),
):
    """List all drivers."""
    drivers = await service.list_all_drivers()
    return StandardResponse(data=drivers)
```

### For Other Services (call user-service via HTTP)

```python
# ride-service/app/config.py
class Settings(BaseSettings):
    USER_SERVICE_URL: str = "http://user-service:8002"
    INTERNAL_SERVICE_TOKEN: str = "internal-secret"

# ride-service/app/dependencies.py
from mediride_common.auth.permissions import ModuleAccessChecker
from app.config import settings

module_checker = ModuleAccessChecker(
    settings.USER_SERVICE_URL,
    settings.INTERNAL_SERVICE_TOKEN
)

# ride-service/app/api/v1/admin_booking_endpoints.py
from app.dependencies import module_checker

@router.get("/admin/bookings")
async def list_bookings(
    _admin: UserClaims = Depends(module_checker.require_module_access("booking_management")),
    service: AdminBookingService = Depends(_get_service),
):
    """List all bookings."""
    bookings = await service.list_all_bookings()
    return StandardResponse(data=bookings)
```

## 3. Module Names Reference

All 16 modules defined in the system:

| Module Name | Display Name | Category | Description |
|-------------|-------------|----------|-------------|
| `analytics_dashboard` | Analytics Dashboard | CORE | Dashboard overview and KPIs |
| `booking_management` | Booking Management | CORE | Ride booking and management |
| `dispatch_center` | Dispatch Center | CORE | Driver dispatch and assignment |
| `gps_tracking` | GPS Tracking | CORE | Real-time location tracking |
| `fleet_management` | Fleet Management | PEOPLE | Fleet companies and applications |
| `driver_management` | Driver Management | PEOPLE | Driver profiles and onboarding |
| `vehicle_management` | Vehicle Management | PEOPLE | Vehicle inventory and maintenance |
| `rider_management` | Rider Management | PEOPLE | Rider profiles and issues |
| `payments_finance` | Payments & Finance | FINANCE | Payment processing and transactions |
| `invoices_billing` | Invoices & Billing | FINANCE | Invoice generation and billing |
| `safety_incidents` | Safety & Incidents | SAFETY | Incident reports and investigations |
| `notifications` | Notifications | SAFETY | System notifications and alerts |
| `support_center` | Support Center | SERVICE | Customer support tickets |
| `dashboard_settings` | Dashboard Settings | ADMINISTRATION | System configuration |
| `roles_permissions` | Roles & Permissions | ADMINISTRATION | Admin role management |
| `system_logs` | System Logs | ADMINISTRATION | Audit logs and activity |

## 4. Seeded Default Roles

### Super Admin (Purple #8B5CF6)
- **Access**: All 16 modules
- **Use Case**: Full system administrators (MediGo staff)

### Operations Manager (Blue #3B82F6)
- **Access**: 8 modules
  - Analytics Dashboard
  - Booking Management
  - Dispatch Center
  - GPS Tracking
  - Fleet Management
  - Driver Management
  - Vehicle Management
  - Safety & Incidents
- **Use Case**: Operations team managing day-to-day ride operations

### Finance Manager (Green #10B981)
- **Access**: 5 modules
  - Analytics Dashboard
  - Payments & Finance
  - Invoices & Billing
  - Driver Management (for payouts)
  - Rider Management (for billing)
- **Use Case**: Finance team handling payments and invoices

### Support Admin (Orange #F59E0B)
- **Access**: 5 modules
  - Support Center
  - Notifications
  - Rider Management
  - Booking Management (view only context)
  - GPS Tracking (for support)
- **Use Case**: Customer support team handling tickets

## 5. API Endpoints

### Public Admin Endpoints

```bash
# Get current user's permissions (for frontend)
GET /users/admin/me/permissions

# List all roles
GET /users/admin/roles

# Create new role
POST /users/admin/roles

# Get role details
GET /users/admin/roles/{role_id}

# Update role
PUT /users/admin/roles/{role_id}

# Delete role
DELETE /users/admin/roles/{role_id}

# Assign role to user
POST /users/admin/roles/assign

# Remove role from user
POST /users/admin/roles/remove

# Get permission matrix
GET /users/admin/permissions/matrix

# Save permissions (bulk update)
POST /users/admin/permissions/save
```

### Internal Endpoints

```bash
# Check if user has module access (called by other services)
POST /users/internal/check-module-access
Headers: X-Internal-Service: internal-secret
Body: { "user_id": "uuid", "module_name": "driver_management" }
Response: { "has_access": true }
```

## 6. Database Schema

### admin_roles
```sql
id              UUID PRIMARY KEY
name            VARCHAR(50) UNIQUE NOT NULL  -- e.g., "super_admin"
display_name    VARCHAR(100) NOT NULL        -- e.g., "Super Admin"
description     VARCHAR(255)
color           VARCHAR(20)                  -- e.g., "#8B5CF6"
is_system       BOOLEAN DEFAULT false
sort_order      INTEGER DEFAULT 999
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

### admin_role_assignments
```sql
id              UUID PRIMARY KEY
user_id         UUID FK(users.id) NOT NULL
role_id         UUID FK(admin_roles.id) NOT NULL
assigned_by     UUID
assigned_at     TIMESTAMPTZ
UNIQUE(user_id, role_id)
```

### module_permissions
```sql
id              UUID PRIMARY KEY
role_id         UUID FK(admin_roles.id) NOT NULL
module_name     VARCHAR(100) NOT NULL
can_access      BOOLEAN DEFAULT true
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
UNIQUE(role_id, module_name)
```

## 7. Testing

### Test Permission Enforcement

```python
# Test unauthorized access
async def test_driver_management_without_permission(client):
    # Login as Finance Admin (no driver_management access)
    token = await login_as_finance_admin()

    response = await client.get(
        "/users/admin/drivers",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]

# Test authorized access
async def test_driver_management_with_permission(client):
    # Login as Operations Admin (has driver_management access)
    token = await login_as_operations_admin()

    response = await client.get(
        "/users/admin/drivers",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
```

## 8. Migration

Run migrations to create the tables:

```bash
# Location service (cities)
docker exec mediride-location-service-1 alembic upgrade head

# User service (roles & permissions)
docker exec mediride-user-service-1 alembic upgrade head
```

## 9. Next Steps

1. **Apply to all admin endpoints**: Replace `require_role([UserRole.ADMIN])` with `require_module_access()`
2. **Add to API Gateway**: Consider adding module enforcement at gateway level
3. **Audit logging**: Log all permission checks for security audit
4. **UI Polish**: Add permission badges, tooltips, and explanations in frontend
5. **Role templates**: Create pre-configured role templates for common use cases

## Security Notes

- **Fail closed**: If permission check fails or errors, deny access
- **Timeout**: HTTP permission checks have 5s timeout
- **Cache**: Consider caching user permissions (with TTL) to reduce DB load
- **Audit**: Log all permission denials for security monitoring
