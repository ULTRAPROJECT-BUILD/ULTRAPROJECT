"""
Google Maps MCP Server
Geocoding, reverse geocoding, place search, place details, directions,
distance matrix, elevation, and timezone via Google Maps Platform APIs.

Uses current (non-legacy) API endpoints:
- Geocoding API (geocode.googleapis.com)
- Places API New (places.googleapis.com/v1)
- Routes API (routes.googleapis.com)
- Elevation API (maps.googleapis.com)
- Timezone API (maps.googleapis.com)
"""

import os
import json
import time
from typing import Optional

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("google-maps")

# --- Configuration ---

API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

GEOCODING_BASE = "https://maps.googleapis.com/maps/api/geocode/json"
PLACES_BASE = "https://places.googleapis.com/v1"
ROUTES_BASE = "https://routes.googleapis.com"
ELEVATION_BASE = "https://maps.googleapis.com/maps/api/elevation/json"
TIMEZONE_BASE = "https://maps.googleapis.com/maps/api/timezone/json"

TIMEOUT = 15  # seconds


def _check_key() -> Optional[str]:
    """Return an error message if API key is missing, else None."""
    if not API_KEY:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not set."
    return None


# --- Tool 1: Geocode ---

@mcp.tool()
def geocode(address: str) -> str:
    """Convert an address or place name to geographic coordinates (latitude/longitude).

    Args:
        address: The street address or place name to geocode (e.g., "1600 Amphitheatre Parkway, Mountain View, CA")

    Returns:
        JSON with latitude, longitude, formatted address, and place_id
    """
    err = _check_key()
    if err:
        return err
    try:
        resp = requests.get(
            GEOCODING_BASE,
            params={"address": address, "key": API_KEY},
            timeout=TIMEOUT,
        )
        data = resp.json()
        if data.get("status") != "OK":
            return f"Geocoding failed: {data.get('status')} — {data.get('error_message', 'no details')}"

        results = []
        for r in data.get("results", [])[:5]:
            loc = r["geometry"]["location"]
            results.append({
                "formatted_address": r.get("formatted_address"),
                "latitude": loc["lat"],
                "longitude": loc["lng"],
                "place_id": r.get("place_id"),
                "types": r.get("types", []),
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Tool 2: Reverse Geocode ---

@mcp.tool()
def reverse_geocode(latitude: float, longitude: float) -> str:
    """Convert geographic coordinates to a human-readable address.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location

    Returns:
        JSON with formatted addresses for the given coordinates
    """
    err = _check_key()
    if err:
        return err
    try:
        resp = requests.get(
            GEOCODING_BASE,
            params={"latlng": f"{latitude},{longitude}", "key": API_KEY},
            timeout=TIMEOUT,
        )
        data = resp.json()
        if data.get("status") != "OK":
            return f"Reverse geocoding failed: {data.get('status')} — {data.get('error_message', 'no details')}"

        results = []
        for r in data.get("results", [])[:5]:
            results.append({
                "formatted_address": r.get("formatted_address"),
                "place_id": r.get("place_id"),
                "types": r.get("types", []),
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Tool 3: Search Places (Text Search) ---

@mcp.tool()
def search_places(
    query: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_meters: int = 5000,
    max_results: int = 10,
) -> str:
    """Search for places using a text query (e.g., "pizza in New York", "dentist near me").

    Args:
        query: Text search query (e.g., "coffee shops in Austin, TX")
        latitude: Optional center latitude for location bias
        longitude: Optional center longitude for location bias
        radius_meters: Search radius in meters when location bias is used (default: 5000)
        max_results: Maximum number of results to return (default: 10, max: 20)

    Returns:
        JSON list of matching places with name, address, rating, and location
    """
    err = _check_key()
    if err:
        return err
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.userRatingCount,"
                "places.types,places.businessStatus,places.websiteUri,"
                "places.nationalPhoneNumber"
            ),
        }
        body = {
            "textQuery": query,
            "maxResultCount": min(max_results, 20),
        }
        if latitude is not None and longitude is not None:
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": float(radius_meters),
                }
            }

        resp = requests.post(
            f"{PLACES_BASE}/places:searchText",
            headers=headers,
            json=body,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return f"Places search failed ({resp.status_code}): {resp.text}"

        data = resp.json()
        results = []
        for p in data.get("places", []):
            loc = p.get("location", {})
            results.append({
                "place_id": p.get("id"),
                "name": p.get("displayName", {}).get("text"),
                "address": p.get("formattedAddress"),
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
                "rating": p.get("rating"),
                "user_ratings": p.get("userRatingCount"),
                "types": p.get("types", []),
                "business_status": p.get("businessStatus"),
                "website": p.get("websiteUri"),
                "phone": p.get("nationalPhoneNumber"),
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Tool 4: Nearby Search ---

@mcp.tool()
def search_nearby(
    latitude: float,
    longitude: float,
    radius_meters: int = 1000,
    place_type: Optional[str] = None,
    max_results: int = 10,
) -> str:
    """Search for places near a specific location by type.

    Args:
        latitude: Center latitude
        longitude: Center longitude
        radius_meters: Search radius in meters (default: 1000, max: 50000)
        place_type: Optional place type filter (e.g., "restaurant", "gas_station", "hospital")
        max_results: Maximum number of results (default: 10, max: 20)

    Returns:
        JSON list of nearby places with name, address, rating, and distance info
    """
    err = _check_key()
    if err:
        return err
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.userRatingCount,"
                "places.types,places.businessStatus,places.websiteUri,"
                "places.nationalPhoneNumber"
            ),
        }
        body = {
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": float(min(radius_meters, 50000)),
                }
            },
            "maxResultCount": min(max_results, 20),
        }
        if place_type:
            body["includedTypes"] = [place_type]

        resp = requests.post(
            f"{PLACES_BASE}/places:searchNearby",
            headers=headers,
            json=body,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return f"Nearby search failed ({resp.status_code}): {resp.text}"

        data = resp.json()
        results = []
        for p in data.get("places", []):
            loc = p.get("location", {})
            results.append({
                "place_id": p.get("id"),
                "name": p.get("displayName", {}).get("text"),
                "address": p.get("formattedAddress"),
                "latitude": loc.get("latitude"),
                "longitude": loc.get("longitude"),
                "rating": p.get("rating"),
                "user_ratings": p.get("userRatingCount"),
                "types": p.get("types", []),
                "business_status": p.get("businessStatus"),
                "website": p.get("websiteUri"),
                "phone": p.get("nationalPhoneNumber"),
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Tool 5: Place Details ---

@mcp.tool()
def place_details(place_id: str) -> str:
    """Get detailed information about a specific place by its place_id.

    Args:
        place_id: The Google Maps place ID (obtained from geocode or search results)

    Returns:
        JSON with full place details: name, address, phone, website, hours, reviews, etc.
    """
    err = _check_key()
    if err:
        return err
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": (
                "id,displayName,formattedAddress,location,rating,"
                "userRatingCount,types,businessStatus,websiteUri,"
                "nationalPhoneNumber,internationalPhoneNumber,"
                "regularOpeningHours,reviews,priceLevel,"
                "editorialSummary,googleMapsUri"
            ),
        }
        resp = requests.get(
            f"{PLACES_BASE}/places/{place_id}",
            headers=headers,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return f"Place details failed ({resp.status_code}): {resp.text}"

        p = resp.json()
        loc = p.get("location", {})
        hours = p.get("regularOpeningHours", {})
        reviews_raw = p.get("reviews", [])

        reviews = []
        for rv in reviews_raw[:5]:
            reviews.append({
                "author": rv.get("authorAttribution", {}).get("displayName"),
                "rating": rv.get("rating"),
                "text": rv.get("text", {}).get("text", ""),
                "relative_time": rv.get("relativePublishTimeDescription"),
            })

        result = {
            "place_id": p.get("id"),
            "name": p.get("displayName", {}).get("text"),
            "address": p.get("formattedAddress"),
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "rating": p.get("rating"),
            "user_ratings": p.get("userRatingCount"),
            "types": p.get("types", []),
            "business_status": p.get("businessStatus"),
            "website": p.get("websiteUri"),
            "phone": p.get("nationalPhoneNumber"),
            "international_phone": p.get("internationalPhoneNumber"),
            "price_level": p.get("priceLevel"),
            "editorial_summary": p.get("editorialSummary", {}).get("text"),
            "google_maps_url": p.get("googleMapsUri"),
            "opening_hours": hours.get("weekdayDescriptions", []),
            "open_now": hours.get("openNow"),
            "reviews": reviews,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Tool 6: Directions (Routes API) ---

@mcp.tool()
def get_directions(
    origin: str,
    destination: str,
    travel_mode: str = "DRIVE",
    avoid_tolls: bool = False,
    avoid_highways: bool = False,
) -> str:
    """Get directions between two locations using the Routes API.

    Args:
        origin: Starting address or "latitude,longitude"
        destination: Ending address or "latitude,longitude"
        travel_mode: Travel mode — DRIVE, BICYCLE, WALK, or TWO_WHEELER (default: DRIVE)
        avoid_tolls: Avoid toll roads (default: false)
        avoid_highways: Avoid highways (default: false)

    Returns:
        JSON with route summary: distance, duration, steps, and polyline
    """
    err = _check_key()
    if err:
        return err
    try:
        def _parse_waypoint(text: str) -> dict:
            """Parse a location string into a Routes API waypoint."""
            parts = text.split(",")
            if len(parts) == 2:
                try:
                    lat = float(parts[0].strip())
                    lng = float(parts[1].strip())
                    return {"location": {"latLng": {"latitude": lat, "longitude": lng}}}
                except ValueError:
                    pass
            return {"address": text}

        modifiers = {}
        if avoid_tolls:
            modifiers["avoidTolls"] = True
        if avoid_highways:
            modifiers["avoidHighways"] = True

        body = {
            "origin": _parse_waypoint(origin),
            "destination": _parse_waypoint(destination),
            "travelMode": travel_mode.upper(),
        }
        if modifiers:
            body["routeModifiers"] = modifiers

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": (
                "routes.distanceMeters,routes.duration,routes.polyline,"
                "routes.legs.distanceMeters,routes.legs.duration,"
                "routes.legs.startLocation,routes.legs.endLocation,"
                "routes.legs.steps.distanceMeters,routes.legs.steps.staticDuration,"
                "routes.legs.steps.navigationInstruction"
            ),
        }

        resp = requests.post(
            f"{ROUTES_BASE}/directions/v2:computeRoutes",
            headers=headers,
            json=body,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return f"Directions failed ({resp.status_code}): {resp.text}"

        data = resp.json()
        routes = data.get("routes", [])
        if not routes:
            return "No routes found between the specified locations."

        route = routes[0]
        legs = route.get("legs", [])

        steps = []
        if legs:
            for step in legs[0].get("steps", []):
                nav = step.get("navigationInstruction", {})
                steps.append({
                    "instruction": nav.get("instructions", ""),
                    "maneuver": nav.get("maneuver", ""),
                    "distance_meters": step.get("distanceMeters"),
                    "duration": step.get("staticDuration"),
                })

        result = {
            "total_distance_meters": route.get("distanceMeters"),
            "total_duration": route.get("duration"),
            "travel_mode": travel_mode.upper(),
            "steps": steps,
            "polyline": route.get("polyline", {}).get("encodedPolyline"),
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Tool 7: Distance Matrix (Routes API) ---

@mcp.tool()
def distance_matrix(
    origins: str,
    destinations: str,
    travel_mode: str = "DRIVE",
) -> str:
    """Calculate travel distances and durations between multiple origins and destinations.

    Args:
        origins: Pipe-separated list of origin addresses or coordinates (e.g., "New York, NY|Boston, MA")
        destinations: Pipe-separated list of destination addresses or coordinates (e.g., "Philadelphia, PA|Washington, DC")
        travel_mode: Travel mode — DRIVE, BICYCLE, WALK, or TWO_WHEELER (default: DRIVE)

    Returns:
        JSON matrix of distances and durations between each origin-destination pair
    """
    err = _check_key()
    if err:
        return err
    try:
        def _parse_waypoints(text: str) -> list:
            waypoints = []
            for item in text.split("|"):
                item = item.strip()
                parts = item.split(",")
                if len(parts) == 2:
                    try:
                        lat = float(parts[0].strip())
                        lng = float(parts[1].strip())
                        waypoints.append({
                            "waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lng}}}
                        })
                        continue
                    except ValueError:
                        pass
                waypoints.append({"waypoint": {"address": item}})
            return waypoints

        body = {
            "origins": _parse_waypoints(origins),
            "destinations": _parse_waypoints(destinations),
            "travelMode": travel_mode.upper(),
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": API_KEY,
            "X-Goog-FieldMask": (
                "originIndex,destinationIndex,distanceMeters,duration,"
                "status,condition"
            ),
        }

        resp = requests.post(
            f"{ROUTES_BASE}/distanceMatrix/v2:computeRouteMatrix",
            headers=headers,
            json=body,
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return f"Distance matrix failed ({resp.status_code}): {resp.text}"

        # Routes API returns streaming JSON array (one object per line)
        # or a regular JSON array
        text = resp.text.strip()
        if text.startswith("["):
            elements = json.loads(text)
        else:
            # Parse newline-delimited JSON
            elements = []
            for line in text.splitlines():
                line = line.strip().rstrip(",")
                if line and line not in ("[", "]"):
                    elements.append(json.loads(line))

        origin_list = [o.strip() for o in origins.split("|")]
        dest_list = [d.strip() for d in destinations.split("|")]

        results = []
        for el in elements:
            oi = el.get("originIndex", 0)
            di = el.get("destinationIndex", 0)
            results.append({
                "origin": origin_list[oi] if oi < len(origin_list) else f"origin_{oi}",
                "destination": dest_list[di] if di < len(dest_list) else f"dest_{di}",
                "distance_meters": el.get("distanceMeters"),
                "duration": el.get("duration"),
                "status": el.get("status"),
                "condition": el.get("condition"),
            })

        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Tool 8: Elevation ---

@mcp.tool()
def get_elevation(locations: str) -> str:
    """Get elevation data for one or more locations.

    Args:
        locations: Pipe-separated coordinates as "lat,lng" pairs (e.g., "39.7391,-104.9847|36.4555,-116.8666")

    Returns:
        JSON with elevation in meters and resolution for each location
    """
    err = _check_key()
    if err:
        return err
    try:
        resp = requests.get(
            ELEVATION_BASE,
            params={
                "locations": locations.replace(" ", ""),
                "key": API_KEY,
            },
            timeout=TIMEOUT,
        )
        data = resp.json()
        if data.get("status") != "OK":
            return f"Elevation failed: {data.get('status')} — {data.get('error_message', 'no details')}"

        results = []
        for r in data.get("results", []):
            loc = r.get("location", {})
            results.append({
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
                "elevation_meters": r.get("elevation"),
                "resolution_meters": r.get("resolution"),
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Tool 9: Timezone ---

@mcp.tool()
def get_timezone(latitude: float, longitude: float) -> str:
    """Get timezone information for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location

    Returns:
        JSON with timezone ID, name, and UTC offsets
    """
    err = _check_key()
    if err:
        return err
    try:
        resp = requests.get(
            TIMEZONE_BASE,
            params={
                "location": f"{latitude},{longitude}",
                "timestamp": str(int(time.time())),
                "key": API_KEY,
            },
            timeout=TIMEOUT,
        )
        data = resp.json()
        if data.get("status") != "OK":
            return f"Timezone failed: {data.get('status')} — {data.get('error_message', 'no details')}"

        result = {
            "timezone_id": data.get("timeZoneId"),
            "timezone_name": data.get("timeZoneName"),
            "raw_offset_seconds": data.get("rawOffset"),
            "dst_offset_seconds": data.get("dstOffset"),
            "total_offset_hours": (data.get("rawOffset", 0) + data.get("dstOffset", 0)) / 3600,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error: {str(e)}"


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
