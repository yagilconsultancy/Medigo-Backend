# Testing Driver Live Location Map

## Overview
A **public test endpoint** has been created to simulate driver GPS location updates without requiring actual mobile devices. This allows testing the real-time tracking map, ETA calculations, and Socket.IO broadcasts.

---

## Endpoint Details

**URL**: `POST /api/v1/tracking/test/simulate-location`

**Authentication**: ❌ **None required** (public endpoint for testing)

**Content-Type**: `application/json`

---

## Request Schema

```json
{
  "driver_id": "uuid-of-driver",
  "latitude": 43.6532,
  "longitude": -79.3832,
  "heading": 180.5,      // Optional: compass direction (0-360 degrees)
  "speed": 45.2          // Optional: speed in km/h
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `driver_id` | UUID | ✅ Yes | Driver's user ID (must have active tracking session) |
| `latitude` | Float | ✅ Yes | GPS latitude (-90 to 90) |
| `longitude` | Float | ✅ Yes | GPS longitude (-180 to 180) |
| `heading` | Float | ❌ No | Compass direction in degrees (0-360) |
| `speed` | Float | ❌ No | Speed in kilometers per hour |

---

## How It Works

### 1. Prerequisites
- Driver must be assigned to a ride
- Ride must have an active tracking session (auto-created when driver is assigned)

### 2. When You Send Location Update
The endpoint will:
1. ✅ Store the location in `location_history` table
2. ✅ Calculate ETA from current position to destination (using Google Maps API)
3. ✅ Update tracking session with current position and ETA
4. ✅ Publish `driver.location.updated` event to RabbitMQ
5. ✅ Broadcast to Socket.IO rooms:
   - **Ride room** (`ride_{ride_id}`) → Rider sees driver approaching
   - **Dispatch center** (`dispatch_center`) → Admin sees all active drivers

### 3. Real-Time Updates
Connected clients will receive:

**Ride-specific update** (event: `location_update`):
```json
{
  "ride_id": "uuid",
  "driver_id": "uuid",
  "latitude": 43.6532,
  "longitude": -79.3832,
  "heading": 180.5,
  "speed": 45.2,
  "eta_minutes": 12.5,
  "distance_remaining_miles": 5.3
}
```

**Dispatch center update** (event: `dispatch_location_update`):
Same payload as above, sent to the dispatch center room for live admin map.

---

## Example Usage

### Using cURL

#### Basic Test (Toronto coordinates)
```bash
curl -X POST http://localhost:8080/api/v1/tracking/test/simulate-location \
  -H "Content-Type: application/json" \
  -d '{
    "driver_id": "YOUR_DRIVER_UUID",
    "latitude": 43.6532,
    "longitude": -79.3832,
    "heading": 90,
    "speed": 50.5
  }'
```

#### Success Response
```json
{
  "success": true,
  "message": "Location update simulated successfully",
  "data": {
    "ride_id": "uuid",
    "driver_id": "uuid",
    "latitude": 43.6532,
    "longitude": -79.3832,
    "heading": 90.0,
    "speed": 50.5,
    "eta_minutes": 12.5,
    "distance_remaining_miles": 5.3
  },
  "timestamp": "2026-04-16T05:30:00Z"
}
```

#### Error Response (No Active Session)
```json
{
  "success": false,
  "message": "No active tracking session found for this driver",
  "data": null,
  "timestamp": "2026-04-16T05:30:00Z"
}
```

---

## Test Scenarios

### Scenario 1: Driver En Route to Pickup
Simulate driver moving toward the pickup location:

```bash
# Starting position (5 km away from pickup)
curl -X POST http://localhost:8080/api/v1/tracking/test/simulate-location \
  -H "Content-Type: application/json" \
  -d '{
    "driver_id": "DRIVER_UUID",
    "latitude": 43.6532,
    "longitude": -79.3832,
    "heading": 90,
    "speed": 50
  }'

# Wait 10 seconds, then move closer
curl -X POST http://localhost:8080/api/v1/tracking/test/simulate-location \
  -H "Content-Type: application/json" \
  -d '{
    "driver_id": "DRIVER_UUID",
    "latitude": 43.6542,
    "longitude": -79.3850,
    "heading": 92,
    "speed": 48
  }'
```

### Scenario 2: Simulate Traffic (Slowing Down)
```bash
# Normal speed
curl -X POST http://localhost:8080/api/v1/tracking/test/simulate-location \
  -H "Content-Type: application/json" \
  -d '{"driver_id": "DRIVER_UUID", "latitude": 43.6532, "longitude": -79.3832, "speed": 50}'

# Hit traffic, slow down
curl -X POST http://localhost:8080/api/v1/tracking/test/simulate-location \
  -H "Content-Type: application/json" \
  -d '{"driver_id": "DRIVER_UUID", "latitude": 43.6535, "longitude": -79.3840, "speed": 15}'
```

### Scenario 3: Driver Stopped at Red Light
```bash
curl -X POST http://localhost:8080/api/v1/tracking/test/simulate-location \
  -H "Content-Type: application/json" \
  -d '{
    "driver_id": "DRIVER_UUID",
    "latitude": 43.6532,
    "longitude": -79.3832,
    "heading": 90,
    "speed": 0
  }'
```

---

## Python Test Script

Save this as `simulate_driver_location.py`:

```python
#!/usr/bin/env python3
"""
Simulate driver GPS location updates for testing the live tracking map.
"""
import requests
import time
import sys
from uuid import UUID

API_BASE = "http://localhost:8080/api/v1"

def simulate_location(driver_id: str, lat: float, lon: float, heading: float = None, speed: float = None):
    """Send a simulated location update."""
    url = f"{API_BASE}/tracking/test/simulate-location"

    payload = {
        "driver_id": driver_id,
        "latitude": lat,
        "longitude": lon,
    }

    if heading is not None:
        payload["heading"] = heading
    if speed is not None:
        payload["speed"] = speed

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            result = data.get("data", {})
            print(f"✅ Location updated: ({lat}, {lon})")
            print(f"   ETA: {result.get('eta_minutes')} min | Distance: {result.get('distance_remaining_miles')} mi")
            return True
        else:
            print(f"❌ Error: {data.get('message')}")
            return False
    else:
        print(f"❌ HTTP {response.status_code}: {response.text}")
        return False

def simulate_route(driver_id: str, waypoints: list, interval: int = 5):
    """
    Simulate a route with multiple waypoints.

    Args:
        driver_id: Driver UUID
        waypoints: List of (lat, lon, heading, speed) tuples
        interval: Seconds between updates
    """
    print(f"🚗 Starting route simulation for driver {driver_id}")
    print(f"📍 {len(waypoints)} waypoints | {interval}s interval\n")

    for i, waypoint in enumerate(waypoints, 1):
        lat, lon, heading, speed = waypoint
        print(f"Waypoint {i}/{len(waypoints)}: ", end="")

        if not simulate_location(driver_id, lat, lon, heading, speed):
            print("Stopping simulation due to error")
            break

        if i < len(waypoints):
            print(f"⏳ Waiting {interval} seconds...\n")
            time.sleep(interval)

    print("\n✅ Route simulation complete!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python simulate_driver_location.py <driver_uuid>")
        sys.exit(1)

    driver_id = sys.argv[1]

    # Validate UUID format
    try:
        UUID(driver_id)
    except ValueError:
        print(f"❌ Invalid UUID: {driver_id}")
        sys.exit(1)

    # Example route: Toronto Union Station → Toronto General Hospital
    # (lat, lon, heading, speed_kmh)
    route = [
        (43.6456, -79.3805, 45, 0),      # Start at Union Station (stopped)
        (43.6460, -79.3795, 45, 35),     # Moving north on Bay St
        (43.6470, -79.3785, 50, 40),     # Continuing north
        (43.6480, -79.3775, 55, 38),     # Approaching College St
        (43.6490, -79.3765, 60, 25),     # Slowing for turn
        (43.6500, -79.3760, 90, 30),     # Turning east on College
        (43.6510, -79.3750, 95, 35),     # Approaching hospital
        (43.6520, -79.3740, 100, 20),    # Entering hospital area
        (43.6525, -79.3735, 105, 5),     # Parking (slow)
        (43.6527, -79.3733, 105, 0),     # Arrived (stopped)
    ]

    simulate_route(driver_id, route, interval=3)
```

### Running the Script

```bash
# Install requests if needed
pip install requests

# Run simulation
python simulate_driver_location.py YOUR_DRIVER_UUID
```

---

## Monitoring Real-Time Updates

### 1. Check Logs
```bash
# Watch tracking service logs
docker-compose logs tracking-service -f | grep "Simulated location"

# Expected output:
# Simulated location update for driver abc-123: (43.6532, -79.3832) ETA: 12.5min
```

### 2. Connect via Socket.IO (Browser)
```javascript
const socket = io('http://localhost:8080/tracking', {
  path: '/api/v1/ws/socket.io',
  auth: { token: 'YOUR_JWT_TOKEN' }
});

// Join specific ride room
socket.emit('join_ride', { ride_id: 'RIDE_UUID' });

// Listen for location updates
socket.on('location_update', (data) => {
  console.log('Driver location:', data.latitude, data.longitude);
  console.log('ETA:', data.eta_minutes, 'minutes');
  // Update map marker here
});
```

### 3. Admin Dispatch Center
```javascript
// Admin can see ALL active drivers
socket.emit('join_dispatch_center');

socket.on('dispatch_location_update', (data) => {
  console.log('Driver', data.driver_id, 'at', data.latitude, data.longitude);
  // Update live map with all drivers
});
```

---

## Common Issues

### ❌ "No active tracking session found"
**Cause**: Driver is not assigned to any ride, or ride doesn't have tracking session

**Solution**:
1. Assign driver to a ride via admin dispatch
2. Tracking session is auto-created when driver is assigned
3. Check: `GET /api/v1/tracking/driver/current` (with driver JWT)

### ❌ "Service unavailable"
**Cause**: tracking-service is not running

**Solution**:
```bash
docker-compose up -d tracking-service
docker-compose logs tracking-service
```

### ❌ ETA shows `null`
**Cause**: Location service couldn't calculate distance (Google Maps API issue or coordinates invalid)

**Solution**: Check location-service logs, verify coordinates are valid GPS coordinates

---

## Integration with Frontend

### React/JavaScript Example
```javascript
const updateDriverLocation = async (driverId, lat, lon, heading, speed) => {
  const response = await fetch('http://localhost:8080/api/v1/tracking/test/simulate-location', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      driver_id: driverId,
      latitude: lat,
      longitude: lon,
      heading: heading,
      speed: speed
    })
  });

  const result = await response.json();

  if (result.success) {
    console.log('Location updated, ETA:', result.data.eta_minutes, 'min');
  } else {
    console.error('Failed:', result.message);
  }
};

// Simulate movement every 5 seconds
setInterval(() => {
  const lat = 43.6532 + Math.random() * 0.01; // Slight random movement
  const lon = -79.3832 + Math.random() * 0.01;
  updateDriverLocation('DRIVER_UUID', lat, lon, 90, 50);
}, 5000);
```

---

## Security Note

⚠️ **This is a TEST endpoint** - it bypasses authentication for development convenience.

**In production**:
- Remove this endpoint OR
- Add IP whitelist (localhost only) OR
- Require an API key

---

## API Documentation

Full interactive API docs available at:
- **Swagger UI**: http://localhost:8080/api/v1/tracking/docs
- **ReDoc**: http://localhost:8080/api/v1/tracking/redoc

Look for the **"Testing"** tag to find the simulate-location endpoint.
