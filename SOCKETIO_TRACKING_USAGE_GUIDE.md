# Socket.IO Tracking - Complete Usage Guide

## Overview

The tracking service provides real-time GPS location updates for rides via Socket.IO.

**Server:** `https://staging.getmedigo.com`
**Namespace:** `/tracking`
**Path:** `/api/v1/ws/socket.io`

---

## Connection Setup

### Basic Connection

```javascript
import io from 'socket.io-client';

const trackingSocket = io('https://staging.getmedigo.com/tracking', {
    path: '/api/v1/ws/socket.io',
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 5
});

trackingSocket.on('connect', () => {
    console.log('Connected to tracking service');
});

trackingSocket.on('disconnect', (reason) => {
    console.log('Disconnected:', reason);
});

trackingSocket.on('connect_error', (error) => {
    console.error('Connection error:', error.message);
});
```

### With Authentication (Optional)

```javascript
const trackingSocket = io('https://staging.getmedigo.com/tracking', {
    path: '/api/v1/ws/socket.io',
    auth: {
        token: 'YOUR_JWT_TOKEN'  // Optional - tracking allows guest connections
    }
});
```

---

## Features & Events

### 1️⃣ Join a Ride Room (Rider Tracking)

**Purpose:** Rider joins to receive real-time driver location updates for their ride.

**Client → Server:**
```javascript
trackingSocket.emit('join_ride', {
    ride_id: '123e4567-e89b-12d3-a456-426614174000'
}, (response) => {
    if (response.error) {
        console.error('Error:', response.error);
    } else {
        console.log('Joined room:', response.room);
        // Response: { status: "joined", room: "ride_123e4567..." }
    }
});
```

**Server → Client (Listen for updates):**
```javascript
trackingSocket.on('location_update', (data) => {
    console.log('Driver location update:', data);
    /*
    {
        ride_id: "123e4567-e89b-12d3-a456-426614174000",
        driver_id: "driver-uuid",
        latitude: 43.6532,
        longitude: -79.3832,
        heading: 180.5,           // Compass direction (0-360)
        speed: 45.2,              // km/h
        eta_minutes: 12.5,        // Estimated time of arrival
        distance_remaining_miles: 5.3,
        timestamp: "2026-05-05T20:00:00Z"
    }
    */

    // Update map marker
    updateDriverMarker(data.latitude, data.longitude, data.heading);
    updateETA(data.eta_minutes);
});
```

### 2️⃣ Leave a Ride Room

```javascript
trackingSocket.emit('leave_ride', {
    ride_id: '123e4567-e89b-12d3-a456-426614174000'
});
```

### 3️⃣ Tracking Status Events

**Tracking Started:**
```javascript
trackingSocket.on('tracking_started', (data) => {
    console.log('Tracking started:', data);
    /*
    {
        ride_id: "123e4567...",
        driver_id: "driver-uuid"
    }
    */

    // Show "Driver is on the way" message
    showNotification('Your driver is on the way!');
});
```

**Tracking Ended:**
```javascript
trackingSocket.on('tracking_ended', (data) => {
    console.log('Tracking ended:', data);
    /*
    {
        ride_id: "123e4567...",
        reason: "ride_completed"  // or "ride_cancelled", "ride_no_show"
    }
    */

    // Hide tracking UI
    hideTrackingMap();
    showRideComplete();
});
```

### 4️⃣ Driver Location Updates (Driver App Only)

**Purpose:** Driver sends their GPS location while on a trip.

**Requirements:**
- Must be authenticated as a driver (role: "driver")
- Must have an active tracking session (assigned to a ride)

**Client → Server:**
```javascript
// Driver app sends location every 5-10 seconds
setInterval(() => {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((position) => {
            trackingSocket.emit('update_location', {
                latitude: position.coords.latitude,
                longitude: position.coords.longitude,
                heading: position.coords.heading || null,
                speed: position.coords.speed || null  // m/s (will be converted)
            }, (response) => {
                if (response.error) {
                    console.error('Location update failed:', response.error);
                } else {
                    console.log('Location updated successfully');
                }
            });
        });
    }
}, 5000);  // Update every 5 seconds
```

**Response:**
```javascript
// Success
{ status: "ok" }

// Error
{ error: "No active tracking session" }
{ error: "Only drivers can send location updates" }
```

### 5️⃣ Admin Dispatch Center (Admin Dashboard)

**Purpose:** Admin sees all active drivers on a live map.

**Requirements:**
- Must be authenticated with role: "admin"

**Client → Server:**
```javascript
trackingSocket.emit('join_dispatch_center', {}, (response) => {
    if (response.error) {
        console.error('Error:', response.error);
        // Response: { error: "Only admins can join dispatch center" }
    } else {
        console.log('Joined dispatch center:', response.room);
        // Response: { status: "joined", room: "dispatch_center" }
    }
});
```

**Server → Client:**
```javascript
trackingSocket.on('dispatch_location_update', (data) => {
    console.log('Driver location (dispatch view):', data);
    /*
    {
        ride_id: "123e4567...",
        driver_id: "driver-uuid",
        latitude: 43.6532,
        longitude: -79.3832,
        heading: 180.5,
        speed: 45.2,
        eta_minutes: 12.5,
        distance_remaining_miles: 5.3,
        timestamp: "2026-05-05T20:00:00Z"
    }
    */

    // Update driver marker on dispatch map
    updateDispatchMap(data.driver_id, data);
});
```

**Leave dispatch center:**
```javascript
trackingSocket.emit('leave_dispatch_center');
```

---

## Complete Examples

### 🚗 Rider App (React)

```javascript
import { useEffect, useState } from 'react';
import io from 'socket.io-client';

function RideTracking({ rideId, pickupLocation, dropoffLocation }) {
    const [driverLocation, setDriverLocation] = useState(null);
    const [eta, setEta] = useState(null);
    const [isTracking, setIsTracking] = useState(false);
    const [socket, setSocket] = useState(null);

    useEffect(() => {
        // Connect to tracking service
        const trackingSocket = io('https://staging.getmedigo.com/tracking', {
            path: '/api/v1/ws/socket.io',
            transports: ['websocket', 'polling']
        });

        trackingSocket.on('connect', () => {
            console.log('Connected to tracking');

            // Join this ride's room
            trackingSocket.emit('join_ride', { ride_id: rideId }, (response) => {
                if (!response.error) {
                    setIsTracking(true);
                }
            });
        });

        // Listen for driver location updates
        trackingSocket.on('location_update', (data) => {
            setDriverLocation({
                lat: data.latitude,
                lng: data.longitude,
                heading: data.heading
            });
            setEta(data.eta_minutes);
        });

        // Tracking started
        trackingSocket.on('tracking_started', (data) => {
            setIsTracking(true);
            showNotification('Your driver is on the way!');
        });

        // Tracking ended
        trackingSocket.on('tracking_ended', (data) => {
            setIsTracking(false);
            if (data.reason === 'ride_completed') {
                showNotification('Ride completed!');
            }
        });

        trackingSocket.on('disconnect', () => {
            console.log('Disconnected from tracking');
            setIsTracking(false);
        });

        setSocket(trackingSocket);

        // Cleanup on unmount
        return () => {
            if (trackingSocket) {
                trackingSocket.emit('leave_ride', { ride_id: rideId });
                trackingSocket.disconnect();
            }
        };
    }, [rideId]);

    return (
        <div className="ride-tracking">
            <h2>Track Your Ride</h2>

            {isTracking ? (
                <>
                    <div className="eta-display">
                        {eta ? (
                            <p>Driver arrives in <strong>{Math.round(eta)} minutes</strong></p>
                        ) : (
                            <p>Calculating arrival time...</p>
                        )}
                    </div>

                    <Map
                        center={driverLocation || pickupLocation}
                        markers={[
                            { position: pickupLocation, icon: 'pickup', label: 'Pickup' },
                            { position: dropoffLocation, icon: 'dropoff', label: 'Dropoff' },
                            driverLocation && {
                                position: driverLocation,
                                icon: 'driver',
                                rotation: driverLocation.heading
                            }
                        ].filter(Boolean)}
                    />
                </>
            ) : (
                <p>Waiting for driver assignment...</p>
            )}
        </div>
    );
}

export default RideTracking;
```

### 🚕 Driver App (React Native)

```javascript
import { useEffect, useState } from 'react';
import io from 'socket.io-client';
import Geolocation from '@react-native-community/geolocation';

function DriverTracking({ driverToken, currentRide }) {
    const [socket, setSocket] = useState(null);
    const [locationInterval, setLocationInterval] = useState(null);

    useEffect(() => {
        if (!currentRide) return;

        // Connect to tracking service
        const trackingSocket = io('https://staging.getmedigo.com/tracking', {
            path: '/api/v1/ws/socket.io',
            auth: { token: driverToken },
            transports: ['websocket'],  // Mobile: WebSocket only
            jsonp: false
        });

        trackingSocket.on('connect', () => {
            console.log('Driver connected to tracking');
            startLocationUpdates(trackingSocket);
        });

        trackingSocket.on('disconnect', () => {
            console.log('Driver disconnected from tracking');
            stopLocationUpdates();
        });

        setSocket(trackingSocket);

        return () => {
            stopLocationUpdates();
            if (trackingSocket) {
                trackingSocket.disconnect();
            }
        };
    }, [currentRide, driverToken]);

    const startLocationUpdates = (socket) => {
        // Send location every 5 seconds
        const interval = setInterval(() => {
            Geolocation.getCurrentPosition(
                (position) => {
                    socket.emit('update_location', {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        heading: position.coords.heading,
                        speed: position.coords.speed * 3.6  // Convert m/s to km/h
                    }, (response) => {
                        if (response.error) {
                            console.error('Location update failed:', response.error);
                        }
                    });
                },
                (error) => console.error('Geolocation error:', error),
                {
                    enableHighAccuracy: true,
                    timeout: 5000,
                    maximumAge: 0
                }
            );
        }, 5000);

        setLocationInterval(interval);
    };

    const stopLocationUpdates = () => {
        if (locationInterval) {
            clearInterval(locationInterval);
            setLocationInterval(null);
        }
    };

    return (
        <View>
            <Text>Active Ride: {currentRide?.id}</Text>
            <Text>GPS Tracking: {socket?.connected ? '✓' : '✗'}</Text>
        </View>
    );
}

export default DriverTracking;
```

### 🗺️ Admin Dispatch Dashboard (Vue.js)

```vue
<template>
    <div class="dispatch-dashboard">
        <h1>Live Dispatch Center</h1>

        <div class="stats">
            <div class="stat-card">
                <h3>{{ activeDrivers.length }}</h3>
                <p>Active Drivers</p>
            </div>
            <div class="stat-card">
                <h3>{{ connectedToDispatch ? 'Live' : 'Offline' }}</h3>
                <p>Connection Status</p>
            </div>
        </div>

        <div class="map-container">
            <Map
                :center="mapCenter"
                :zoom="12"
                :markers="driverMarkers"
            />
        </div>

        <div class="driver-list">
            <h3>Active Drivers</h3>
            <div v-for="driver in activeDrivers" :key="driver.driver_id" class="driver-item">
                <span>Driver {{ driver.driver_id.substring(0, 8) }}</span>
                <span>Ride {{ driver.ride_id.substring(0, 8) }}</span>
                <span>ETA: {{ Math.round(driver.eta_minutes) }}min</span>
                <span>Speed: {{ Math.round(driver.speed) }} km/h</span>
            </div>
        </div>
    </div>
</template>

<script>
import io from 'socket.io-client';

export default {
    name: 'DispatchDashboard',
    data() {
        return {
            socket: null,
            connectedToDispatch: false,
            activeDrivers: [],
            mapCenter: { lat: 43.6532, lng: -79.3832 }  // Toronto
        };
    },
    computed: {
        driverMarkers() {
            return this.activeDrivers.map(driver => ({
                position: { lat: driver.latitude, lng: driver.longitude },
                icon: 'driver-icon',
                rotation: driver.heading,
                label: `ETA: ${Math.round(driver.eta_minutes)}min`
            }));
        }
    },
    mounted() {
        this.connectToDispatch();
    },
    beforeUnmount() {
        if (this.socket) {
            this.socket.emit('leave_dispatch_center');
            this.socket.disconnect();
        }
    },
    methods: {
        connectToDispatch() {
            const adminToken = localStorage.getItem('admin_token');

            this.socket = io('https://staging.getmedigo.com/tracking', {
                path: '/api/v1/ws/socket.io',
                auth: { token: adminToken }
            });

            this.socket.on('connect', () => {
                console.log('Connected to tracking');

                // Join dispatch center
                this.socket.emit('join_dispatch_center', {}, (response) => {
                    if (response.error) {
                        console.error('Failed to join dispatch center:', response.error);
                        this.$toast.error('Admin access required');
                    } else {
                        this.connectedToDispatch = true;
                        this.$toast.success('Connected to dispatch center');
                    }
                });
            });

            this.socket.on('disconnect', () => {
                this.connectedToDispatch = false;
                this.$toast.warning('Disconnected from dispatch center');
            });

            // Listen for all driver location updates
            this.socket.on('dispatch_location_update', (data) => {
                this.updateDriverLocation(data);
            });

            // Listen for tracking ended (remove driver from map)
            this.socket.on('tracking_ended', (data) => {
                this.removeDriver(data.driver_id);
            });
        },

        updateDriverLocation(data) {
            const index = this.activeDrivers.findIndex(
                d => d.driver_id === data.driver_id
            );

            if (index !== -1) {
                // Update existing driver
                this.activeDrivers[index] = data;
            } else {
                // Add new driver
                this.activeDrivers.push(data);
            }
        },

        removeDriver(driverId) {
            this.activeDrivers = this.activeDrivers.filter(
                d => d.driver_id !== driverId
            );
        }
    }
};
</script>

<style scoped>
.dispatch-dashboard {
    padding: 20px;
}

.stats {
    display: flex;
    gap: 20px;
    margin-bottom: 20px;
}

.stat-card {
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.map-container {
    height: 600px;
    margin-bottom: 20px;
}

.driver-list {
    background: white;
    padding: 20px;
    border-radius: 8px;
}

.driver-item {
    display: flex;
    justify-content: space-between;
    padding: 10px;
    border-bottom: 1px solid #eee;
}
</style>
```

---

## Testing Without Real GPS

### Simulate Driver Location Updates

You can test the tracking system without a real driver by using the test endpoint:

**HTTP REST Endpoint:**
```bash
POST https://staging.getmedigo.com/api/v1/tracking/test/simulate-location
Content-Type: application/json

{
    "driver_id": "driver-uuid",
    "latitude": 43.6532,
    "longitude": -79.3832,
    "heading": 90,
    "speed": 50
}
```

**JavaScript Simulation:**
```javascript
// Simulate driver moving along a route
async function simulateDriverRoute(driverId, waypoints) {
    for (const waypoint of waypoints) {
        await fetch('https://staging.getmedigo.com/api/v1/tracking/test/simulate-location', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                driver_id: driverId,
                latitude: waypoint.lat,
                longitude: waypoint.lng,
                heading: waypoint.heading,
                speed: waypoint.speed
            })
        });

        // Wait 3 seconds before next update
        await new Promise(resolve => setTimeout(resolve, 3000));
    }
}

// Simulate route from Union Station to Toronto General Hospital
const route = [
    { lat: 43.6456, lng: -79.3805, heading: 45, speed: 0 },
    { lat: 43.6460, lng: -79.3795, heading: 45, speed: 35 },
    { lat: 43.6470, lng: -79.3785, heading: 50, speed: 40 },
    { lat: 43.6500, lng: -79.3760, heading: 90, speed: 30 },
    { lat: 43.6527, lng: -79.3733, heading: 105, speed: 0 }
];

simulateDriverRoute('driver-uuid-here', route);
```

---

## Event Summary

| Event Name | Direction | Who Can Use | Purpose |
|------------|-----------|-------------|---------|
| `join_ride` | Client → Server | Anyone | Join a ride room to receive location updates |
| `leave_ride` | Client → Server | Anyone | Leave a ride room |
| `update_location` | Client → Server | Drivers only | Send GPS location update |
| `join_dispatch_center` | Client → Server | Admins only | Join dispatch center to see all drivers |
| `leave_dispatch_center` | Client → Server | Admins only | Leave dispatch center |
| `location_update` | Server → Client | Ride room members | Driver location update for specific ride |
| `dispatch_location_update` | Server → Client | Dispatch center | Location update for all active drivers |
| `tracking_started` | Server → Client | Ride room members | Tracking session started for ride |
| `tracking_ended` | Server → Client | Ride room members | Tracking session ended for ride |

---

## Best Practices

### 1. Connection Management

```javascript
// Good: Reuse socket connection
const socket = io('https://staging.getmedigo.com/tracking', {
    path: '/api/v1/ws/socket.io'
});

// Bad: Creating new connection for each component
// Don't do this!
```

### 2. Memory Leaks Prevention

```javascript
// Always cleanup on unmount
useEffect(() => {
    const socket = io(...);

    return () => {
        socket.disconnect();  // ← IMPORTANT
    };
}, []);
```

### 3. Error Handling

```javascript
trackingSocket.on('connect_error', (error) => {
    console.error('Connection error:', error);
    showErrorMessage('Unable to connect to tracking service');
});

trackingSocket.emit('join_ride', { ride_id }, (response) => {
    if (response.error) {
        handleError(response.error);
    }
});
```

### 4. Reconnection Strategy

```javascript
const socket = io('https://staging.getmedigo.com/tracking', {
    path: '/api/v1/ws/socket.io',
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000
});

socket.on('reconnect', (attemptNumber) => {
    console.log('Reconnected after', attemptNumber, 'attempts');
    // Re-join ride room after reconnection
    socket.emit('join_ride', { ride_id: currentRideId });
});
```

### 5. Performance

```javascript
// Driver location updates: Send every 5-10 seconds (not every second!)
const UPDATE_INTERVAL = 5000;

setInterval(() => {
    sendLocationUpdate();
}, UPDATE_INTERVAL);
```

---

## Troubleshooting

### "No active tracking session" error

**Cause:** Driver not assigned to a ride
**Solution:** Ride must be assigned to driver first (via admin API)

### Location updates not received

**Check:**
1. Joined the correct ride room: `socket.emit('join_ride', { ride_id })`
2. Driver has active tracking session
3. Socket is connected: `socket.connected === true`

### ETA shows `null`

**Cause:** Location service couldn't calculate distance
**Solution:** Check that pickup/dropoff coordinates are valid

### Connection keeps dropping

**Check:**
1. Network stability
2. Server logs: `docker logs -f mediride-tracking-service-1`
3. Nginx WebSocket configuration is correct

---

## Next Steps

1. ✅ Test connection with [socket_client_example.html](socket_client_example.html)
2. ✅ Integrate into rider app (use React example)
3. ✅ Integrate into driver app (use React Native example)
4. ✅ Build admin dispatch dashboard (use Vue example)
5. ✅ Test with simulated location updates
6. ✅ Deploy to production

Need help with integration? Check [SOCKETIO_PRODUCTION_SETUP.md](SOCKETIO_PRODUCTION_SETUP.md)
