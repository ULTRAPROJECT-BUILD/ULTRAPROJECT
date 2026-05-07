"""
Eventbrite MCP Server
Event management and marketing via Eventbrite API v3 — list events, get details,
attendees, ticket classes, venues, and search organization events.
"""

import os
import json
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("eventbrite")

# --- Configuration ---

API_TOKEN = os.environ.get("EVENTBRITE_API_TOKEN", "")
BASE_URL = "https://www.eventbriteapi.com/v3"


def _headers() -> dict:
    """Return authorization headers for Eventbrite API."""
    return {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }


def _get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to the Eventbrite API with error handling."""
    if not API_TOKEN:
        return {"error": "EVENTBRITE_API_TOKEN environment variable is not set"}
    url = f"{BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        body = ""
        try:
            body = e.response.json().get("error_description", str(e))
        except Exception:
            body = str(e)
        return {"error": f"HTTP {status}: {body}"}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out after 30 seconds"}
    except requests.exceptions.ConnectionError:
        return {"error": "Connection error — check network connectivity"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def _get_organization_id() -> str:
    """Get the primary organization ID for the authenticated user."""
    data = _get("/users/me/organizations/")
    if "error" in data:
        return ""
    orgs = data.get("organizations", [])
    if orgs:
        return orgs[0].get("id", "")
    return ""


# --- Tools ---


@mcp.tool()
def list_events(status: str = "live", page: int = 1) -> str:
    """List the authenticated user's events from their primary organization.

    Args:
        status: Event status filter — "live", "draft", "started", "ended", "completed", "canceled", or "all" (default: "live")
        page: Page number for pagination (default: 1)

    Returns:
        JSON with list of events including id, name, status, start/end times, and pagination info
    """
    org_id = _get_organization_id()
    if not org_id:
        return json.dumps({"error": "Could not determine organization ID. Check your API token."})

    params = {"page": page, "page_size": 50}
    if status != "all":
        params["status"] = status

    data = _get(f"/organizations/{org_id}/events/", params=params)
    if "error" in data:
        return json.dumps(data)

    events = []
    for ev in data.get("events", []):
        events.append({
            "id": ev.get("id"),
            "name": ev.get("name", {}).get("text", ""),
            "status": ev.get("status"),
            "url": ev.get("url"),
            "start": ev.get("start", {}).get("local"),
            "end": ev.get("end", {}).get("local"),
            "created": ev.get("created"),
            "capacity": ev.get("capacity"),
            "is_free": ev.get("is_free"),
        })

    pagination = data.get("pagination", {})
    return json.dumps({
        "events": events,
        "pagination": {
            "page_number": pagination.get("page_number"),
            "page_count": pagination.get("page_count"),
            "page_size": pagination.get("page_size"),
            "object_count": pagination.get("object_count"),
            "has_more_items": pagination.get("has_more_items", False),
        }
    }, indent=2)


@mcp.tool()
def get_event(event_id: str) -> str:
    """Get full details for a specific event including name, description, dates, venue, capacity, and ticket info.

    Args:
        event_id: The Eventbrite event ID

    Returns:
        JSON with complete event details
    """
    if not event_id:
        return json.dumps({"error": "event_id is required"})

    data = _get(f"/events/{event_id}/", params={"expand": "venue,ticket_classes,category,organizer"})
    if "error" in data:
        return json.dumps(data)

    venue = data.get("venue") or {}
    address = venue.get("address", {})
    organizer = data.get("organizer") or {}
    category = data.get("category") or {}

    ticket_classes = []
    for tc in data.get("ticket_classes", []):
        ticket_classes.append({
            "id": tc.get("id"),
            "name": tc.get("name"),
            "free": tc.get("free"),
            "cost": tc.get("cost", {}).get("display") if tc.get("cost") else "Free",
            "quantity_total": tc.get("quantity_total"),
            "quantity_sold": tc.get("quantity_sold"),
            "on_sale_status": tc.get("on_sale_status"),
            "sales_start": tc.get("sales_start"),
            "sales_end": tc.get("sales_end"),
        })

    result = {
        "id": data.get("id"),
        "name": data.get("name", {}).get("text", ""),
        "description": data.get("description", {}).get("text", ""),
        "summary": data.get("summary", ""),
        "url": data.get("url"),
        "status": data.get("status"),
        "start": data.get("start", {}).get("local"),
        "end": data.get("end", {}).get("local"),
        "timezone": data.get("start", {}).get("timezone"),
        "created": data.get("created"),
        "changed": data.get("changed"),
        "capacity": data.get("capacity"),
        "is_free": data.get("is_free"),
        "is_online_event": data.get("online_event"),
        "category": {
            "id": category.get("id"),
            "name": category.get("name"),
        },
        "organizer": {
            "id": organizer.get("id"),
            "name": organizer.get("name"),
            "url": organizer.get("url"),
        },
        "venue": {
            "id": venue.get("id"),
            "name": venue.get("name"),
            "address": address.get("localized_address_display", ""),
            "city": address.get("city", ""),
            "region": address.get("region", ""),
            "country": address.get("country", ""),
            "latitude": address.get("latitude"),
            "longitude": address.get("longitude"),
        },
        "ticket_classes": ticket_classes,
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def get_attendees(event_id: str, page: int = 1, status: str = "attending") -> str:
    """List attendees/orders for a specific event with pagination.

    Args:
        event_id: The Eventbrite event ID
        page: Page number for pagination (default: 1)
        status: Attendee status filter — "attending", "checked_in", "not_attending", or "all" (default: "attending")

    Returns:
        JSON with list of attendees including name, email, ticket type, order info, and pagination
    """
    if not event_id:
        return json.dumps({"error": "event_id is required"})

    params = {"page": page, "page_size": 50}
    if status != "all":
        params["status"] = status

    data = _get(f"/events/{event_id}/attendees/", params=params)
    if "error" in data:
        return json.dumps(data)

    attendees = []
    for att in data.get("attendees", []):
        profile = att.get("profile", {})
        costs = att.get("costs", {})
        attendees.append({
            "id": att.get("id"),
            "order_id": att.get("order_id"),
            "name": profile.get("name", ""),
            "email": profile.get("email", ""),
            "status": att.get("status"),
            "ticket_class_name": att.get("ticket_class_name", ""),
            "ticket_class_id": att.get("ticket_class_id"),
            "checked_in": att.get("checked_in", False),
            "cancelled": att.get("cancelled", False),
            "refunded": att.get("refunded", False),
            "cost_gross": costs.get("gross", {}).get("display") if costs.get("gross") else None,
            "created": att.get("created"),
        })

    pagination = data.get("pagination", {})
    return json.dumps({
        "attendees": attendees,
        "total_count": pagination.get("object_count"),
        "pagination": {
            "page_number": pagination.get("page_number"),
            "page_count": pagination.get("page_count"),
            "page_size": pagination.get("page_size"),
            "object_count": pagination.get("object_count"),
            "has_more_items": pagination.get("has_more_items", False),
        }
    }, indent=2)


@mcp.tool()
def get_ticket_classes(event_id: str) -> str:
    """Get ticket types, pricing, and availability for a specific event.

    Args:
        event_id: The Eventbrite event ID

    Returns:
        JSON with list of ticket classes including name, price, quantity, sales status, and dates
    """
    if not event_id:
        return json.dumps({"error": "event_id is required"})

    data = _get(f"/events/{event_id}/ticket_classes/")
    if "error" in data:
        return json.dumps(data)

    ticket_classes = []
    for tc in data.get("ticket_classes", []):
        ticket_classes.append({
            "id": tc.get("id"),
            "name": tc.get("name"),
            "description": tc.get("description"),
            "free": tc.get("free"),
            "cost": tc.get("cost", {}).get("display") if tc.get("cost") else "Free",
            "fee": tc.get("fee", {}).get("display") if tc.get("fee") else None,
            "tax": tc.get("tax", {}).get("display") if tc.get("tax") else None,
            "quantity_total": tc.get("quantity_total"),
            "quantity_sold": tc.get("quantity_sold"),
            "on_sale_status": tc.get("on_sale_status"),
            "sales_start": tc.get("sales_start"),
            "sales_end": tc.get("sales_end"),
            "minimum_quantity": tc.get("minimum_quantity"),
            "maximum_quantity": tc.get("maximum_quantity"),
            "hidden": tc.get("hidden", False),
            "include_fee": tc.get("include_fee", False),
        })

    return json.dumps({
        "event_id": event_id,
        "ticket_classes": ticket_classes,
        "total": len(ticket_classes),
    }, indent=2)


@mcp.tool()
def get_venue(venue_id: str) -> str:
    """Get venue details including name, full address, and coordinates.

    Args:
        venue_id: The Eventbrite venue ID

    Returns:
        JSON with venue name, address, city, region, country, latitude, longitude
    """
    if not venue_id:
        return json.dumps({"error": "venue_id is required"})

    data = _get(f"/venues/{venue_id}/")
    if "error" in data:
        return json.dumps(data)

    address = data.get("address", {})
    result = {
        "id": data.get("id"),
        "name": data.get("name"),
        "address_1": address.get("address_1", ""),
        "address_2": address.get("address_2", ""),
        "city": address.get("city", ""),
        "region": address.get("region", ""),
        "postal_code": address.get("postal_code", ""),
        "country": address.get("country", ""),
        "localized_address": address.get("localized_address_display", ""),
        "latitude": address.get("latitude"),
        "longitude": address.get("longitude"),
        "capacity": data.get("capacity"),
        "age_restriction": data.get("age_restriction"),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def search_events(query: str = "", location: str = "", date_range: str = "", page: int = 1) -> str:
    """Search organization events by keyword, location, or date range.

    Note: Eventbrite deprecated the public event search API in 2020. This tool
    searches within the authenticated user's organization events only. For public
    event discovery, use the Eventbrite website directly.

    Args:
        query: Search keyword to filter events by name (case-insensitive substring match)
        location: Filter by venue city (case-insensitive substring match)
        date_range: Filter by date — "today", "this_week", "this_month", "next_month", or "past"
        page: Page number for pagination (default: 1)

    Returns:
        JSON with matching events from the user's organization
    """
    org_id = _get_organization_id()
    if not org_id:
        return json.dumps({"error": "Could not determine organization ID. Check your API token."})

    # Fetch all statuses so we can search across everything
    params = {"page": page, "page_size": 50, "expand": "venue"}

    # Use time_filter if date_range is provided
    time_filter_map = {
        "past": "past",
        "current_future": "current_future",
    }

    # Eventbrite org events endpoint supports time_filter and name_filter
    if query:
        params["name_filter"] = query
    if date_range in time_filter_map:
        params["time_filter"] = time_filter_map[date_range]
    elif date_range in ("today", "this_week", "this_month", "next_month"):
        # These require client-side filtering after fetch
        params["time_filter"] = "current_future"

    data = _get(f"/organizations/{org_id}/events/", params=params)
    if "error" in data:
        return json.dumps(data)

    events = []
    for ev in data.get("events", []):
        venue = ev.get("venue") or {}
        venue_address = venue.get("address", {})
        venue_city = venue_address.get("city", "")

        # Apply location filter (client-side)
        if location and location.lower() not in venue_city.lower():
            full_address = venue_address.get("localized_address_display", "")
            if location.lower() not in full_address.lower():
                continue

        # Apply date_range filter (client-side for granular filters)
        if date_range in ("today", "this_week", "this_month", "next_month"):
            from datetime import datetime, timedelta
            start_str = ev.get("start", {}).get("local", "")
            if start_str:
                try:
                    event_date = datetime.fromisoformat(start_str)
                    now = datetime.now()
                    if date_range == "today" and event_date.date() != now.date():
                        continue
                    elif date_range == "this_week":
                        week_end = now + timedelta(days=(6 - now.weekday()))
                        if not (now.date() <= event_date.date() <= week_end.date()):
                            continue
                    elif date_range == "this_month":
                        if event_date.month != now.month or event_date.year != now.year:
                            continue
                    elif date_range == "next_month":
                        next_m = now.month + 1 if now.month < 12 else 1
                        next_y = now.year if now.month < 12 else now.year + 1
                        if event_date.month != next_m or event_date.year != next_y:
                            continue
                except (ValueError, TypeError):
                    pass

        events.append({
            "id": ev.get("id"),
            "name": ev.get("name", {}).get("text", ""),
            "status": ev.get("status"),
            "url": ev.get("url"),
            "start": ev.get("start", {}).get("local"),
            "end": ev.get("end", {}).get("local"),
            "venue_name": venue.get("name", ""),
            "venue_city": venue_city,
            "capacity": ev.get("capacity"),
            "is_free": ev.get("is_free"),
        })

    pagination = data.get("pagination", {})
    return json.dumps({
        "query": query or "(all)",
        "location_filter": location or "(any)",
        "date_filter": date_range or "(any)",
        "results": events,
        "result_count": len(events),
        "pagination": {
            "page_number": pagination.get("page_number"),
            "page_count": pagination.get("page_count"),
            "has_more_items": pagination.get("has_more_items", False),
        },
        "note": "Searches within your organization events only. Public event search was deprecated by Eventbrite in 2020."
    }, indent=2)


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
