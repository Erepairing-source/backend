"""
Routing service for map directions
"""
from typing import Optional
import httpx

from app.core.config import settings


class RoutingService:
    def __init__(self):
        self.provider = (settings.MAPS_PROVIDER or "mapbox").lower()

    async def get_route(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
        if self.provider == "google":
            return await self._google_route(origin_lat, origin_lng, dest_lat, dest_lng)
        return await self._mapbox_route(origin_lat, origin_lng, dest_lat, dest_lng)

    async def _mapbox_route(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
        if not settings.MAPBOX_ACCESS_TOKEN:
            return {"error": "Mapbox access token not configured"}
        url = (
            "https://api.mapbox.com/directions/v5/mapbox/driving/"
            f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        )
        params = {
            "access_token": settings.MAPBOX_ACCESS_TOKEN,
            "overview": "full",
            "geometries": "geojson"
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        if not data.get("routes"):
            return {"error": "No route found"}
        route = data["routes"][0]
        return {
            "provider": "mapbox",
            "distance_m": route.get("distance"),
            "duration_s": route.get("duration"),
            "geometry": route.get("geometry"),
            "summary": route.get("legs", [{}])[0].get("summary")
        }

    async def _google_route(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
        if not settings.GOOGLE_MAPS_API_KEY:
            return {"error": "Google Maps API key not configured"}
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": f"{origin_lat},{origin_lng}",
            "destination": f"{dest_lat},{dest_lng}",
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        if data.get("status") != "OK":
            return {"error": data.get("error_message") or data.get("status")}
        route = data["routes"][0]
        leg = route["legs"][0]
        return {
            "provider": "google",
            "distance_m": leg["distance"]["value"],
            "duration_s": leg["duration"]["value"],
            "polyline": route.get("overview_polyline", {}).get("points")
        }

    async def geocode_address(self, address: str):
        if self.provider == "google":
            return await self._google_geocode(address)
        return await self._mapbox_geocode(address)

    async def _mapbox_geocode(self, address: str):
        if not settings.MAPBOX_ACCESS_TOKEN:
            return {"error": "Mapbox access token not configured"}
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{address}.json"
        params = {
            "access_token": settings.MAPBOX_ACCESS_TOKEN,
            "limit": 1
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        if not data.get("features"):
            return {"error": "No results"}
        feature = data["features"][0]
        lng, lat = feature["center"]
        return {
            "provider": "mapbox",
            "latitude": lat,
            "longitude": lng,
            "formatted_address": feature.get("place_name")
        }

    async def _google_geocode(self, address: str):
        if not settings.GOOGLE_MAPS_API_KEY:
            return {"error": "Google Maps API key not configured"}
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": settings.GOOGLE_MAPS_API_KEY
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        if data.get("status") != "OK":
            return {"error": data.get("error_message") or data.get("status")}
        result = data["results"][0]
        location = result["geometry"]["location"]
        return {
            "provider": "google",
            "latitude": location["lat"],
            "longitude": location["lng"],
            "formatted_address": result.get("formatted_address")
        }

    def get_static_map_url(self, latitude: float, longitude: float, zoom: int = 14, width: int = 600, height: int = 400):
        if self.provider == "google":
            if not settings.GOOGLE_MAPS_API_KEY:
                return None
            return (
                "https://maps.googleapis.com/maps/api/staticmap"
                f"?center={latitude},{longitude}&zoom={zoom}"
                f"&size={width}x{height}&markers={latitude},{longitude}"
                f"&key={settings.GOOGLE_MAPS_API_KEY}"
            )
        if not settings.MAPBOX_ACCESS_TOKEN:
            return None
        return (
            "https://api.mapbox.com/styles/v1/mapbox/streets-v12/static/"
            f"pin-s+ff0000({longitude},{latitude})/"
            f"{longitude},{latitude},{zoom},0/{width}x{height}"
            f"?access_token={settings.MAPBOX_ACCESS_TOKEN}"
        )
