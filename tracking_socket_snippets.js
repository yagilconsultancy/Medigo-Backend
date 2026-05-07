/**
 * MediRide Socket.IO Tracking - Copy-Paste Snippets
 *
 * Quick implementation examples for tracking features
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

const SOCKET_CONFIG = {
    local: {
        server: 'http://localhost:8080',
        path: '/api/v1/ws/socket.io'
    },
    staging: {
        server: 'https://staging.getmedigo.com',
        path: '/api/v1/ws/socket.io'
    },
    production: {
        server: 'https://api.getmedigo.com',  // Update when production is ready
        path: '/api/v1/ws/socket.io'
    }
};

// Select environment
const ENV = 'staging';  // Change to 'local' or 'production'
const config = SOCKET_CONFIG[ENV];

// ============================================================================
// 1. RIDER APP - Track Your Ride
// ============================================================================

function initRiderTracking(rideId, onLocationUpdate, onTrackingStatusChange) {
    // Import: import io from 'socket.io-client';

    const socket = io(`${config.server}/tracking`, {
        path: config.path,
        transports: ['websocket', 'polling']
    });

    socket.on('connect', () => {
        console.log('✓ Connected to tracking');

        // Join your ride room
        socket.emit('join_ride', { ride_id: rideId }, (response) => {
            if (response.error) {
                console.error('Join failed:', response.error);
            } else {
                console.log('✓ Joined ride room:', response.room);
            }
        });
    });

    // Receive driver location updates
    socket.on('location_update', (data) => {
        /*
        data = {
            ride_id: "...",
            driver_id: "...",
            latitude: 43.6532,
            longitude: -79.3832,
            heading: 180.5,
            speed: 45.2,
            eta_minutes: 12.5,
            distance_remaining_miles: 5.3,
            timestamp: "2026-05-05T20:00:00Z"
        }
        */
        onLocationUpdate(data);
    });

    // Tracking started
    socket.on('tracking_started', (data) => {
        console.log('🚀 Driver is on the way!');
        onTrackingStatusChange('started', data);
    });

    // Tracking ended
    socket.on('tracking_ended', (data) => {
        console.log('🏁 Ride completed');
        onTrackingStatusChange('ended', data);
    });

    socket.on('disconnect', () => {
        console.log('✗ Disconnected');
    });

    // Return cleanup function
    return () => {
        socket.emit('leave_ride', { ride_id: rideId });
        socket.disconnect();
    };
}

// USAGE:
/*
const cleanup = initRiderTracking(
    'ride-uuid-here',

    // onLocationUpdate callback
    (data) => {
        // Update map marker
        map.setDriverPosition(data.latitude, data.longitude);
        document.getElementById('eta').textContent = `${Math.round(data.eta_minutes)} min`;
    },

    // onTrackingStatusChange callback
    (status, data) => {
        if (status === 'started') {
            showNotification('Your driver is on the way!');
        } else if (status === 'ended') {
            showNotification('Ride completed!');
        }
    }
);

// When component unmounts:
cleanup();
*/

// ============================================================================
// 2. DRIVER APP - Send Location Updates
// ============================================================================

function initDriverTracking(driverToken) {
    const socket = io(`${config.server}/tracking`, {
        path: config.path,
        auth: { token: driverToken },
        transports: ['websocket']  // Mobile: WebSocket only
    });

    let locationInterval = null;

    socket.on('connect', () => {
        console.log('✓ Driver connected to tracking');
        startSendingLocation();
    });

    socket.on('disconnect', () => {
        console.log('✗ Driver disconnected');
        stopSendingLocation();
    });

    function startSendingLocation() {
        // Send location every 5 seconds
        locationInterval = setInterval(() => {
            // Get current GPS position
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    socket.emit('update_location', {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        heading: position.coords.heading || null,
                        speed: position.coords.speed ? position.coords.speed * 3.6 : null  // m/s → km/h
                    }, (response) => {
                        if (response.error) {
                            console.error('Location update failed:', response.error);
                        } else {
                            console.log('✓ Location sent');
                        }
                    });
                },
                (error) => console.error('GPS error:', error),
                { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
            );
        }, 5000);
    }

    function stopSendingLocation() {
        if (locationInterval) {
            clearInterval(locationInterval);
            locationInterval = null;
        }
    }

    return () => {
        stopSendingLocation();
        socket.disconnect();
    };
}

// USAGE:
/*
const cleanup = initDriverTracking('driver-jwt-token-here');

// When ride ends or driver logs out:
cleanup();
*/

// ============================================================================
// 3. ADMIN DASHBOARD - Dispatch Center (All Drivers)
// ============================================================================

function initDispatchCenter(adminToken, onDriverUpdate) {
    const socket = io(`${config.server}/tracking`, {
        path: config.path,
        auth: { token: adminToken }
    });

    const activeDrivers = new Map();  // driver_id → driver data

    socket.on('connect', () => {
        console.log('✓ Connected to tracking');

        // Join dispatch center
        socket.emit('join_dispatch_center', {}, (response) => {
            if (response.error) {
                console.error('Failed to join dispatch:', response.error);
                alert('Admin access required');
            } else {
                console.log('✓ Joined dispatch center');
            }
        });
    });

    // Receive location updates for ALL active drivers
    socket.on('dispatch_location_update', (data) => {
        activeDrivers.set(data.driver_id, data);
        onDriverUpdate(Array.from(activeDrivers.values()));
    });

    // Driver finished ride
    socket.on('tracking_ended', (data) => {
        activeDrivers.delete(data.driver_id);
        onDriverUpdate(Array.from(activeDrivers.values()));
    });

    socket.on('disconnect', () => {
        console.log('✗ Disconnected from dispatch');
    });

    return () => {
        socket.emit('leave_dispatch_center');
        socket.disconnect();
    };
}

// USAGE:
/*
const cleanup = initDispatchCenter(
    'admin-jwt-token-here',

    // onDriverUpdate callback
    (drivers) => {
        console.log(`${drivers.length} active drivers`);

        // Update map with all driver markers
        drivers.forEach(driver => {
            map.updateDriverMarker(driver.driver_id, {
                lat: driver.latitude,
                lng: driver.longitude,
                heading: driver.heading,
                eta: driver.eta_minutes
            });
        });
    }
);

// When admin logs out:
cleanup();
*/

// ============================================================================
// 4. REACT HOOK - useRideTracking
// ============================================================================

import { useEffect, useState } from 'react';
import io from 'socket.io-client';

export function useRideTracking(rideId) {
    const [driverLocation, setDriverLocation] = useState(null);
    const [eta, setEta] = useState(null);
    const [trackingStatus, setTrackingStatus] = useState('disconnected'); // disconnected | connecting | active | ended
    const [socket, setSocket] = useState(null);

    useEffect(() => {
        if (!rideId) return;

        setTrackingStatus('connecting');

        const trackingSocket = io(`${config.server}/tracking`, {
            path: config.path,
            transports: ['websocket', 'polling']
        });

        trackingSocket.on('connect', () => {
            trackingSocket.emit('join_ride', { ride_id: rideId }, (response) => {
                if (!response.error) {
                    setTrackingStatus('active');
                }
            });
        });

        trackingSocket.on('location_update', (data) => {
            setDriverLocation({
                lat: data.latitude,
                lng: data.longitude,
                heading: data.heading,
                speed: data.speed
            });
            setEta(data.eta_minutes);
        });

        trackingSocket.on('tracking_started', () => {
            setTrackingStatus('active');
        });

        trackingSocket.on('tracking_ended', () => {
            setTrackingStatus('ended');
        });

        trackingSocket.on('disconnect', () => {
            setTrackingStatus('disconnected');
        });

        setSocket(trackingSocket);

        return () => {
            trackingSocket.emit('leave_ride', { ride_id: rideId });
            trackingSocket.disconnect();
        };
    }, [rideId]);

    return { driverLocation, eta, trackingStatus, socket };
}

// USAGE IN COMPONENT:
/*
function RideTrackingPage({ rideId }) {
    const { driverLocation, eta, trackingStatus } = useRideTracking(rideId);

    return (
        <div>
            <p>Status: {trackingStatus}</p>
            {eta && <p>Driver arrives in {Math.round(eta)} minutes</p>}

            {driverLocation && (
                <Map
                    center={driverLocation}
                    markers={[{
                        position: driverLocation,
                        icon: 'driver-car',
                        rotation: driverLocation.heading
                    }]}
                />
            )}
        </div>
    );
}
*/

// ============================================================================
// 5. SIMULATED TESTING - Without Real GPS
// ============================================================================

/**
 * Simulate driver movement for testing
 * Useful for testing the rider app without a real driver
 */
async function simulateDriverMovement(driverId, route) {
    for (let i = 0; i < route.length; i++) {
        const point = route[i];

        const response = await fetch(`${config.server}/api/v1/tracking/test/simulate-location`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                driver_id: driverId,
                latitude: point.lat,
                longitude: point.lng,
                heading: point.heading || 0,
                speed: point.speed || 40
            })
        });

        const result = await response.json();
        console.log(`Point ${i + 1}/${route.length}:`, result.success ? '✓' : '✗');

        // Wait 3 seconds before next point
        if (i < route.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 3000));
        }
    }
}

// USAGE:
/*
// Toronto: Union Station → Toronto General Hospital
const testRoute = [
    { lat: 43.6456, lng: -79.3805, heading: 45, speed: 0 },     // Start
    { lat: 43.6460, lng: -79.3795, heading: 45, speed: 35 },
    { lat: 43.6470, lng: -79.3785, heading: 50, speed: 40 },
    { lat: 43.6480, lng: -79.3775, heading: 55, speed: 38 },
    { lat: 43.6500, lng: -79.3760, heading: 90, speed: 30 },
    { lat: 43.6527, lng: -79.3733, heading: 105, speed: 0 }     // Arrived
];

simulateDriverMovement('driver-uuid-here', testRoute);
*/

// ============================================================================
// 6. VANILLA JAVASCRIPT - No Framework
// ============================================================================

(function vanillaTrackingExample() {
    // Load Socket.IO from CDN first:
    // <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>

    const rideId = 'your-ride-id';

    const socket = io('https://staging.getmedigo.com/tracking', {
        path: '/api/v1/ws/socket.io'
    });

    socket.on('connect', function() {
        console.log('Connected!');

        socket.emit('join_ride', { ride_id: rideId }, function(response) {
            console.log('Joined:', response);
        });
    });

    socket.on('location_update', function(data) {
        document.getElementById('latitude').textContent = data.latitude;
        document.getElementById('longitude').textContent = data.longitude;
        document.getElementById('eta').textContent = Math.round(data.eta_minutes) + ' min';
    });

    socket.on('tracking_started', function() {
        document.getElementById('status').textContent = 'Driver is on the way!';
    });

    socket.on('tracking_ended', function() {
        document.getElementById('status').textContent = 'Ride completed';
    });
})();

// ============================================================================
// 7. ERROR HANDLING & RECONNECTION
// ============================================================================

function createRobustConnection(namespace = '/tracking', token = null) {
    const socket = io(`${config.server}${namespace}`, {
        path: config.path,
        auth: token ? { token } : undefined,
        transports: ['websocket', 'polling'],

        // Reconnection settings
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        timeout: 10000
    });

    // Connection lifecycle
    socket.on('connect', () => {
        console.log('✓ Connected (attempt:', socket.io.reconnectionAttempts(), ')');
    });

    socket.on('disconnect', (reason) => {
        console.log('✗ Disconnected:', reason);

        if (reason === 'io server disconnect') {
            // Server kicked us out, try to reconnect
            socket.connect();
        }
    });

    socket.on('connect_error', (error) => {
        console.error('Connection error:', error.message);
    });

    socket.on('reconnect', (attemptNumber) => {
        console.log('✓ Reconnected after', attemptNumber, 'attempts');
        // Re-join rooms after reconnection
        rejoinRooms(socket);
    });

    socket.on('reconnect_failed', () => {
        console.error('✗ Failed to reconnect after max attempts');
        showErrorModal('Unable to connect to tracking service. Please refresh the page.');
    });

    return socket;
}

function rejoinRooms(socket) {
    // Re-join ride room after reconnection
    const currentRideId = localStorage.getItem('current_ride_id');
    if (currentRideId) {
        socket.emit('join_ride', { ride_id: currentRideId });
    }
}

// ============================================================================
// EXPORTS (for ES modules)
// ============================================================================

export {
    SOCKET_CONFIG,
    initRiderTracking,
    initDriverTracking,
    initDispatchCenter,
    useRideTracking,
    simulateDriverMovement,
    createRobustConnection
};
