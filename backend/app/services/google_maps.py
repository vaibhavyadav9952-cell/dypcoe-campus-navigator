"""
services/google_maps.py - Async Google Maps Routes API v2 wrapper.
"""

import httpx
from app.core.config import settings

ROUTES_API_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


async def get_walking_route(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
) -> dict:
    """
    Calls Google Maps Routes API v2 (computeRoutes) with WALK travelMode.
    Returns: {distance_meters, duration_seconds, polyline}
    Raises: httpx.HTTPError on API failure
    """
    if not settings.GOOGLE_MAPS_API_KEY:
        raise ValueError("GOOGLE_MAPS_API_KEY not configured")

    payload = {
        "origin": {
            "location": {"latLng": {"latitude": origin_lat, "longitude": origin_lng}}
        },
        "destination": {
            "location": {"latLng": {"latitude": dest_lat, "longitude": dest_lng}}
        },
        "travelMode": "WALK",
        "computeAlternativeRoutes": False,
        "units": "METRIC",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": (
            "routes.distanceMeters,routes.duration,"
            "routes.polyline.encodedPolyline"
        ),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(ROUTES_API_URL, json=payload, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    if not data.get("routes"):
        raise ValueError("Google Maps returned no routes")

    route = data["routes"][0]
    distance_m = route.get("distanceMeters", 0)
    duration_str = route.get("duration", "0s")
    duration_s = int(duration_str.rstrip("s")) if isinstance(duration_str, str) else int(duration_str)
    polyline = route.get("polyline", {}).get("encodedPolyline", "")

    return {
        "distance_meters": distance_m,
        "duration_seconds": duration_s,
        "polyline": polyline,
    }
