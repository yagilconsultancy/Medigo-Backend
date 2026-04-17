#!/usr/bin/env python3
"""
Simulate driver GPS location updates for testing the live tracking map.

Usage:
    python simulate_driver_location.py <driver_uuid>

Example:
    python simulate_driver_location.py 123e4567-e89b-12d3-a456-426614174000
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

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                result = data.get("data", {})
                print(f"✅ Location updated: ({lat:.6f}, {lon:.6f})")
                eta = result.get("eta_minutes")
                dist = result.get("distance_remaining_miles")
                if eta is not None and dist is not None:
                    print(f"   ETA: {eta:.1f} min | Distance: {dist:.2f} mi | Speed: {speed or 0} km/h")
                else:
                    print(f"   Speed: {speed or 0} km/h (ETA calculation unavailable)")
                return True
            else:
                print(f"❌ Error: {data.get('message')}")
                return False
        else:
            print(f"❌ HTTP {response.status_code}: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False


def simulate_route(driver_id: str, waypoints: list, interval: int = 5):
    """
    Simulate a route with multiple waypoints.

    Args:
        driver_id: Driver UUID
        waypoints: List of (lat, lon, heading, speed) tuples
        interval: Seconds between updates
    """
    print(f"\n🚗 Starting route simulation for driver {driver_id}")
    print(f"📍 {len(waypoints)} waypoints | {interval}s interval")
    print("=" * 70)

    for i, waypoint in enumerate(waypoints, 1):
        lat, lon, heading, speed = waypoint
        print(f"\nWaypoint {i}/{len(waypoints)}: ", end="")

        if not simulate_location(driver_id, lat, lon, heading, speed):
            print("\n⚠️  Stopping simulation due to error")
            break

        if i < len(waypoints):
            print(f"⏳ Waiting {interval} seconds...")
            time.sleep(interval)

    print("\n" + "=" * 70)
    print("✅ Route simulation complete!\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n❌ Missing driver UUID")
        print("\nUsage:")
        print("  python simulate_driver_location.py <driver_uuid>")
        print("\nExample:")
        print("  python simulate_driver_location.py 123e4567-e89b-12d3-a456-426614174000")
        print()
        sys.exit(1)

    driver_id = sys.argv[1]

    # Validate UUID format
    try:
        UUID(driver_id)
    except ValueError:
        print(f"\n❌ Invalid UUID format: {driver_id}")
        print("Please provide a valid UUID (e.g., 123e4567-e89b-12d3-a456-426614174000)\n")
        sys.exit(1)

    # Example route: Toronto Union Station → Toronto General Hospital
    # Format: (latitude, longitude, heading_degrees, speed_kmh)
    print("\n📋 Route: Toronto Union Station → Toronto General Hospital")
    print("   Total distance: ~2.5 km | Estimated time: ~30 seconds\n")

    route = [
        (43.6456, -79.3805, 45, 0),      # 🚗 Start at Union Station (stopped)
        (43.6460, -79.3795, 45, 35),     # 🚗 Moving north on Bay St
        (43.6470, -79.3785, 50, 40),     # 🚗 Continuing north
        (43.6480, -79.3775, 55, 38),     # 🚗 Approaching College St
        (43.6490, -79.3765, 60, 25),     # 🚗 Slowing for turn
        (43.6500, -79.3760, 90, 30),     # 🚗 Turning east on College
        (43.6510, -79.3750, 95, 35),     # 🚗 Approaching hospital
        (43.6520, -79.3740, 100, 20),    # 🚗 Entering hospital area
        (43.6525, -79.3735, 105, 5),     # 🚗 Parking (slow)
        (43.6527, -79.3733, 105, 0),     # 🏁 Arrived (stopped)
    ]

    # Run the simulation with 3-second intervals
    simulate_route(driver_id, route, interval=3)
