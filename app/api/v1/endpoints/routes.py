"""
Routing endpoints
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from app.core.permissions import get_current_user
from app.models.user import User
from app.services.routing import RoutingService

router = APIRouter()
routing_service = RoutingService()


@router.get("/directions")
async def get_directions(
    origin_lat: float = Query(...),
    origin_lng: float = Query(...),
    dest_lat: float = Query(...),
    dest_lng: float = Query(...),
    current_user: User = Depends(get_current_user)
):
    """Get route between two coordinates"""
    try:
        result = await routing_service.get_route(origin_lat, origin_lng, dest_lat, dest_lng)
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/geocode")
async def geocode_address(
    address: str = Query(..., min_length=3),
    current_user: User = Depends(get_current_user)
):
    """Geocode address to latitude/longitude"""
    result = await routing_service.geocode_address(address)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/static-map")
def get_static_map(
    latitude: float = Query(...),
    longitude: float = Query(...),
    zoom: int = Query(14),
    current_user: User = Depends(get_current_user)
):
    """Return static map image URL"""
    url = routing_service.get_static_map_url(latitude, longitude, zoom=zoom)
    if not url:
        raise HTTPException(status_code=400, detail="Map provider not configured")
    return {"map_url": url}


@router.get("/static-map-image")
async def get_static_map_image(
    latitude: float = Query(...),
    longitude: float = Query(...),
    zoom: int = Query(14),
    current_user: User = Depends(get_current_user),
):
    """Proxy static map tile (for <img> with Authorization; avoids hotlink/CORS on OSM/Google)."""
    url = routing_service.get_static_map_url(latitude, longitude, zoom=zoom)
    if not url:
        raise HTTPException(status_code=400, detail="Map provider not configured")
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            upstream = await client.get(
                url,
                headers={"User-Agent": "eRepairing/1.0 (static-map proxy)"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not load map image: {exc}") from exc
    if upstream.status_code >= 400:
        raise HTTPException(status_code=502, detail="Map provider returned an error")
    content_type = upstream.headers.get("content-type") or "image/png"
    return Response(content=upstream.content, media_type=content_type)
