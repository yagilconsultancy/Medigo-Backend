# Socket.IO Integration for Live Dispatch Map

Complete guide for connecting to Socket.IO and receiving real-time location updates for all active trips.

## 1. Connection Setup

### Install Socket.IO Client

```bash
npm install socket.io-client
# or
yarn add socket.io-client
```

### Basic Connection

```javascript
import { io } from 'socket.io-client';

// Connect to tracking service via API Gateway
const socket = io('http://localhost:8000/tracking', {
  auth: {
    token: localStorage.getItem('adminToken') // Your JWT token
  },
  transports: ['websocket', 'polling'],
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionAttempts: 5
});
```

## 2. Complete Dispatch Center Integration

### React Example

```javascript
import React, { useEffect, useState, useRef } from 'react';
import { io } from 'socket.io-client';

const DispatchMap = () => {
  const [activeTrips, setActiveTrips] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef(null);
  const mapRef = useRef(null);
  const markersRef = useRef({});

  useEffect(() => {
    initializeDispatchCenter();

    return () => {
      // Cleanup on unmount
      if (socketRef.current) {
        socketRef.current.emit('leave_dispatch_center');
        socketRef.current.disconnect();
      }
    };
  }, []);

  const initializeDispatchCenter = async () => {
    // 1. Fetch all active trips
    await loadActiveTrips();

    // 2. Connect to Socket.IO
    connectToTracking();
  };

  const loadActiveTrips = async () => {
    try {
      const response = await fetch('/api/v1/rides/admin/dispatch/active-trips', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
        }
      });

      const { data: trips } = await response.json();
      setActiveTrips(trips);

      // Add markers to map
      trips.forEach(trip => {
        addTripMarker(trip);
      });
    } catch (error) {
      console.error('Failed to load active trips:', error);
    }
  };

  const connectToTracking = () => {
    const socket = io('http://localhost:8000/tracking', {
      auth: {
        token: localStorage.getItem('adminToken')
      },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    });

    socketRef.current = socket;

    // Connection events
    socket.on('connect', () => {
      console.log('Socket.IO connected:', socket.id);
      setIsConnected(true);

      // Join dispatch center room
      socket.emit('join_dispatch_center', (response) => {
        console.log('Joined dispatch center:', response);
        // Response: { status: 'joined', room: 'dispatch_center' }
      });
    });

    socket.on('disconnect', () => {
      console.log('Socket.IO disconnected');
      setIsConnected(false);
    });

    socket.on('connect_error', (error) => {
      console.error('Connection error:', error);
      setIsConnected(false);
    });

    // Tracking events
    socket.on('dispatch_location_update', (data) => {
      console.log('Location update:', data);
      handleLocationUpdate(data);
    });

    socket.on('tracking_started', (data) => {
      console.log('Tracking started:', data);
      // Refresh active trips or add new trip marker
      loadActiveTrips();
    });

    socket.on('tracking_ended', (data) => {
      console.log('Tracking ended:', data);
      // Remove trip marker from map
      removeTripMarker(data.ride_id);
    });
  };

  const handleLocationUpdate = (data) => {
    /*
    data = {
      ride_id: "uuid",
      driver_id: "uuid",
      latitude: 43.6532,
      longitude: -79.3832,
      heading: 45,       // 0-360 degrees
      speed: 33.5,       // mph
      timestamp: "2026-04-11T19:45:30Z"
    }
    */

    const marker = markersRef.current[data.ride_id];
    if (marker) {
      // Update marker position
      marker.setPosition({
        lat: data.latitude,
        lng: data.longitude
      });

      // Update marker icon with rotation based on heading
      const icon = getRotatedVehicleIcon(data.heading);
      marker.setIcon(icon);

      // Update trip info in state
      setActiveTrips(prev => prev.map(trip =>
        trip.trip_id === data.ride_id
          ? {
              ...trip,
              latitude: data.latitude,
              longitude: data.longitude,
              heading: data.heading,
              speed_mph: data.speed,
              last_update: data.timestamp
            }
          : trip
      ));
    }
  };

  const addTripMarker = (trip) => {
    if (!mapRef.current) return;

    // Create marker (example with Google Maps)
    const marker = new window.google.maps.Marker({
      position: { lat: trip.latitude, lng: trip.longitude },
      map: mapRef.current,
      title: `${trip.booking_number} - ${trip.driver_name}`,
      icon: getVehicleIcon(trip.ride_type, trip.heading || 0)
    });

    // Add info window
    const infoWindow = new window.google.maps.InfoWindow({
      content: `
        <div style="padding: 10px;">
          <h3>${trip.booking_number}</h3>
          <p><strong>Driver:</strong> ${trip.driver_name}</p>
          <p><strong>Rider:</strong> ${trip.rider_name}</p>
          <p><strong>Status:</strong> ${trip.status}</p>
          <p><strong>From:</strong> ${trip.pickup_address}</p>
          <p><strong>To:</strong> ${trip.destination_address}</p>
          <p><strong>Progress:</strong> ${trip.progress_percent}%</p>
        </div>
      `
    });

    marker.addListener('click', () => {
      infoWindow.open(mapRef.current, marker);
    });

    markersRef.current[trip.trip_id] = marker;
  };

  const removeTripMarker = (tripId) => {
    const marker = markersRef.current[tripId];
    if (marker) {
      marker.setMap(null);
      delete markersRef.current[tripId];
    }

    setActiveTrips(prev => prev.filter(trip => trip.trip_id !== tripId));
  };

  const getVehicleIcon = (rideType, heading) => {
    // Map vehicle icons with rotation
    const icons = {
      ambulatory: '/icons/car-ambulatory.svg',
      wheelchair: '/icons/car-wav.svg',
      stretcher: '/icons/car-stretcher.svg'
    };

    return {
      url: icons[rideType] || icons.ambulatory,
      scaledSize: new window.google.maps.Size(40, 40),
      anchor: new window.google.maps.Point(20, 20),
      rotation: heading // Rotate icon based on heading
    };
  };

  const getRotatedVehicleIcon = (heading) => {
    return {
      url: '/icons/car-active.svg',
      scaledSize: new window.google.maps.Size(40, 40),
      anchor: new window.google.maps.Point(20, 20),
      rotation: heading
    };
  };

  return (
    <div className="dispatch-center">
      <div className="status-bar">
        <span className={isConnected ? 'connected' : 'disconnected'}>
          {isConnected ? '● Connected' : '○ Disconnected'}
        </span>
        <span>Active Trips: {activeTrips.length}</span>
      </div>

      <div id="map" ref={mapRef} style={{ width: '100%', height: '100vh' }}>
        {/* Google Maps will render here */}
      </div>

      <div className="trip-list">
        <h3>Active Trips</h3>
        {activeTrips.map(trip => (
          <div key={trip.trip_id} className="trip-card">
            <div className="trip-header">
              <strong>{trip.booking_number}</strong>
              <span className={`status status-${trip.status}`}>
                {trip.status}
              </span>
            </div>
            <div className="trip-details">
              <p>Driver: {trip.driver_name}</p>
              <p>Rider: {trip.rider_name}</p>
              <p>Progress: {trip.progress_percent}%</p>
              {trip.speed_mph && <p>Speed: {trip.speed_mph} mph</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DispatchMap;
```

## 3. Vanilla JavaScript Example

```javascript
// Initialize Socket.IO connection
const socket = io('http://localhost:8000/tracking', {
  auth: {
    token: localStorage.getItem('adminToken')
  }
});

// Connection handlers
socket.on('connect', () => {
  console.log('Connected to tracking service');

  // Join dispatch center room
  socket.emit('join_dispatch_center', (response) => {
    console.log('Joined dispatch center:', response);
  });
});

socket.on('disconnect', () => {
  console.log('Disconnected from tracking service');
});

// Location update handler
socket.on('dispatch_location_update', (data) => {
  console.log('Location update:', data);

  // Update marker on map
  updateDriverLocation(data.ride_id, {
    lat: data.latitude,
    lng: data.longitude,
    heading: data.heading,
    speed: data.speed
  });
});

// Tracking lifecycle handlers
socket.on('tracking_started', (data) => {
  console.log('New trip started:', data);
  fetchAndAddTrip(data.ride_id);
});

socket.on('tracking_ended', (data) => {
  console.log('Trip ended:', data);
  removeTrip(data.ride_id);
});

// Load initial active trips
async function loadActiveTrips() {
  const response = await fetch('/api/v1/rides/admin/dispatch/active-trips', {
    headers: {
      'Authorization': `Bearer ${localStorage.getItem('adminToken')}`
    }
  });

  const { data: trips } = await response.json();

  trips.forEach(trip => {
    addMarkerToMap(trip);
  });
}

// Update driver location on map
function updateDriverLocation(tripId, location) {
  const marker = markers[tripId];
  if (marker) {
    marker.setPosition({ lat: location.lat, lng: location.lng });
    marker.setIcon(getRotatedIcon(location.heading));
  }
}
```

## 4. Socket.IO Events Reference

### Client → Server Events

| Event | Payload | Description |
|-------|---------|-------------|
| `join_dispatch_center` | none | Join dispatch center room to receive all trip updates |
| `leave_dispatch_center` | none | Leave dispatch center room |
| `join_ride` | `{ ride_id: "uuid" }` | Join specific ride room (for individual trip tracking) |
| `leave_ride` | `{ ride_id: "uuid" }` | Leave specific ride room |

### Server → Client Events

| Event | Payload | Description |
|-------|---------|-------------|
| `dispatch_location_update` | See below | Real-time location update for any active trip |
| `tracking_started` | `{ ride_id, driver_id }` | Tracking started for a new trip |
| `tracking_ended` | `{ ride_id, reason }` | Tracking ended for a trip |
| `connect` | - | Socket.IO connection established |
| `disconnect` | - | Socket.IO connection lost |
| `connect_error` | `error` | Connection error occurred |

### `dispatch_location_update` Payload

```javascript
{
  ride_id: "uuid",           // Trip identifier
  driver_id: "uuid",         // Driver identifier
  latitude: 43.6532,         // Current latitude
  longitude: -79.3832,       // Current longitude
  heading: 45,               // Direction (0-360 degrees, 0=North)
  speed: 33.5,               // Current speed in mph
  timestamp: "ISO8601"       // Update timestamp
}
```

## 5. Error Handling

```javascript
socket.on('connect_error', (error) => {
  console.error('Connection failed:', error);

  // Show error to user
  showNotification('Connection to tracking service failed', 'error');

  // Try to reconnect with new token if auth failed
  if (error.message === 'Authentication required') {
    refreshToken().then(newToken => {
      socket.auth.token = newToken;
      socket.connect();
    });
  }
});

socket.on('error', (error) => {
  console.error('Socket error:', error);
});

// Handle join errors
socket.emit('join_dispatch_center', (response) => {
  if (response.error) {
    console.error('Failed to join dispatch center:', response.error);
    showNotification(response.error, 'error');
  } else {
    console.log('Successfully joined dispatch center');
  }
});
```

## 6. Reconnection Strategy

```javascript
const socket = io('http://localhost:8000/tracking', {
  auth: {
    token: localStorage.getItem('adminToken')
  },
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 20000
});

socket.on('reconnect', (attemptNumber) => {
  console.log('Reconnected after', attemptNumber, 'attempts');

  // Rejoin dispatch center room
  socket.emit('join_dispatch_center');

  // Reload active trips
  loadActiveTrips();
});

socket.on('reconnect_attempt', (attemptNumber) => {
  console.log('Reconnection attempt', attemptNumber);
});

socket.on('reconnect_failed', () => {
  console.error('Failed to reconnect');
  showNotification('Unable to connect to tracking service', 'error');
});
```

## 7. Environment Configuration

```javascript
// config.js
const SOCKET_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const TRACKING_NAMESPACE = '/tracking';

export const socket = io(`${SOCKET_URL}${TRACKING_NAMESPACE}`, {
  auth: {
    token: () => localStorage.getItem('adminToken') // Function for dynamic token
  },
  transports: ['websocket', 'polling']
});
```

## 8. Complete Flow Diagram

```
┌─────────────────┐
│  Admin Opens    │
│  Dispatch Map   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Fetch Active Trips               │
│    GET /admin/dispatch/active-trips │
│    Returns: All trips with status   │
│    driver_arrived or in_progress    │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 2. Add Trip Markers to Map          │
│    For each trip, create marker     │
│    with position, icon, info        │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 3. Connect to Socket.IO             │
│    io('http://localhost:8000/       │
│       tracking', { auth: {...} })   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 4. Join Dispatch Center Room        │
│    socket.emit('join_dispatch_      │
│    center')                          │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 5. Listen for Location Updates      │
│    socket.on('dispatch_location_    │
│    update', handleUpdate)            │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 6. Update Marker Positions          │
│    On each update:                   │
│    - Move marker                     │
│    - Rotate icon                     │
│    - Update trip info                │
└─────────────────────────────────────┘
```

## 9. Testing Socket.IO Connection

```bash
# Install wscat for testing
npm install -g wscat

# Connect to Socket.IO (WebSocket mode)
wscat -c "ws://localhost:8000/socket.io/?EIO=4&transport=websocket"

# After connection, send auth and join
42["join_dispatch_center"]
```

## 10. Production Considerations

```javascript
// Use secure WebSocket in production
const SOCKET_URL = process.env.NODE_ENV === 'production'
  ? 'https://api.mediride.com'
  : 'http://localhost:8000';

const socket = io(`${SOCKET_URL}/tracking`, {
  auth: {
    token: getToken()
  },
  // Use only WebSocket in production for better performance
  transports: process.env.NODE_ENV === 'production'
    ? ['websocket']
    : ['websocket', 'polling'],
  secure: process.env.NODE_ENV === 'production',
  rejectUnauthorized: true
});
```

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/rides/admin/dispatch/active-trips` | GET | Get all active trips |
| Socket.IO: `http://localhost:8000/tracking` | WebSocket | Real-time tracking namespace |

## Troubleshooting

**Connection Refused:**
- Check if tracking-service is running: `docker-compose ps tracking-service`
- Verify JWT token is valid
- Check CORS settings

**Not Receiving Updates:**
- Verify you joined dispatch_center room: `socket.emit('join_dispatch_center')`
- Check if any trips are active with status `driver_arrived` or `in_progress`
- Verify driver is sending location updates

**Markers Not Updating:**
- Check browser console for Socket.IO events
- Verify `dispatch_location_update` event handler is attached
- Ensure marker reference exists in markersRef
