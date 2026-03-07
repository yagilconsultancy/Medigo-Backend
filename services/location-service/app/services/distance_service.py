import logging

import googlemaps

logger = logging.getLogger(__name__)

# Conversion factor
KM_TO_MILES = 0.621371


class DistanceService:
    def __init__(self, gmaps_client: googlemaps.Client | None):
        self.gmaps = gmaps_client

    async def calculate_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict | None:
        """Calculate distance and duration between two points."""
        if not self.gmaps:
            logger.warning("Google Maps client not configured")
            return self._estimate_haversine(origin_lat, origin_lng, dest_lat, dest_lng)

        try:
            result = self.gmaps.distance_matrix(
                origins=[(origin_lat, origin_lng)],
                destinations=[(dest_lat, dest_lng)],
                mode="driving",
                units="imperial",
            )

            if result["status"] != "OK":
                return self._estimate_haversine(origin_lat, origin_lng, dest_lat, dest_lng)

            element = result["rows"][0]["elements"][0]
            if element["status"] != "OK":
                return self._estimate_haversine(origin_lat, origin_lng, dest_lat, dest_lng)

            distance_meters = element["distance"]["value"]
            duration_seconds = element["duration"]["value"]

            return {
                "distance_miles": round(distance_meters / 1609.344, 2),
                "distance_km": round(distance_meters / 1000, 2),
                "duration_minutes": round(duration_seconds / 60, 1),
                "duration_text": element["duration"]["text"],
                "distance_text": element["distance"]["text"],
                "source": "google",
            }
        except Exception as e:
            logger.error(f"Distance calculation failed: {e}")
            return self._estimate_haversine(origin_lat, origin_lng, dest_lat, dest_lng)

    def _estimate_haversine(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict:
        """Fallback: estimate distance using Haversine formula."""
        import math

        R = 3959  # Earth's radius in miles

        lat1 = math.radians(origin_lat)
        lat2 = math.radians(dest_lat)
        dlat = math.radians(dest_lat - origin_lat)
        dlng = math.radians(dest_lng - origin_lng)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance_miles = round(R * c, 2)
        # Rough estimate: average 30 mph in urban areas
        duration_minutes = round(distance_miles / 30 * 60, 1)

        return {
            "distance_miles": distance_miles,
            "distance_km": round(distance_miles / KM_TO_MILES, 2),
            "duration_minutes": duration_minutes,
            "duration_text": f"{int(duration_minutes)} mins",
            "distance_text": f"{distance_miles} mi",
            "source": "estimate",
        }

    async def calculate_eta(
        self,
        driver_lat: float,
        driver_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> dict | None:
        """Calculate ETA from driver to destination."""
        result = await self.calculate_distance(driver_lat, driver_lng, dest_lat, dest_lng)
        if result:
            return {
                "eta_minutes": result["duration_minutes"],
                "distance_miles": result["distance_miles"],
            }
        return None
