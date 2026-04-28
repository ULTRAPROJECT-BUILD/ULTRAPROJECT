# google-maps MCP Server

Geocoding, reverse geocoding, place search, place details, directions,
distance matrix, elevation, and timezone via Google Maps Platform APIs.

Uses current (non-legacy) API endpoints: Geocoding API, Places API (New),
Routes API (replaces deprecated Directions/Distance Matrix), Elevation API,
Timezone API.

## Setup

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| GOOGLE_MAPS_API_KEY | Yes | Google Maps Platform API key with Geocoding, Places (New), Routes, Elevation, and Timezone APIs enabled |

### Enable Required APIs

In Google Cloud Console, enable these APIs:
1. Geocoding API
2. Places API (New)
3. Routes API
4. Elevation API
5. Time Zone API

### Free Tier

Google Maps Platform provides $200/month free credit, which covers approximately:
- 40,000 geocoding requests
- 28,500 map loads
- 40,000 directions requests

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Tools

| Tool | Description |
|------|-------------|
| geocode | Convert an address or place name to latitude/longitude coordinates |
| reverse_geocode | Convert lat/lng coordinates to a human-readable address |
| search_places | Text-based place search (e.g., "pizza in New York") with optional location bias |
| search_nearby | Find places near a specific location by type (restaurant, hospital, etc.) |
| place_details | Get full details for a place by its place_id (hours, reviews, phone, website) |
| get_directions | Get turn-by-turn directions between two locations via Routes API |
| distance_matrix | Calculate distances and durations between multiple origins and destinations |
| get_elevation | Get elevation data for one or more coordinates |
| get_timezone | Get timezone information for a location |

## Registration

Add to `.mcp.json`:
```json
{
  "google-maps": {
    "type": "stdio",
    "command": "python3",
    "args": ["/path/to/vault/clients/_platform/mcps/google-maps/server.py"],
    "env": {
      "GOOGLE_MAPS_API_KEY": ""
    }
  }
}
```
