"""
Calendar MCP Server (CalDAV)

Provides calendar tools over the CalDAV protocol:
  - list_calendars    — list all calendars on the connected server
  - list_events       — list events with optional date range filter
  - get_event         — get full event details by UID
  - create_event      — create a new calendar event
  - update_event      — update an existing event
  - delete_event      — delete an event by UID
  - check_availability — return free/busy times in a date range

Works with any CalDAV provider:
  - Google Calendar (app password + CalDAV URL)
  - Apple iCloud (app password + CalDAV URL)
  - Fastmail (app password + CalDAV URL)
  - Any standards-compliant CalDAV server

Credentials are read from environment variables:
    CALDAV_URL      - CalDAV server URL
    CALDAV_USERNAME - account username / email
    CALDAV_PASSWORD - app-specific password
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, date
from typing import Optional

import caldav
from icalendar import Calendar, Event, vDatetime

from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CALDAV_URL: str = os.environ.get("CALDAV_URL", "")
CALDAV_USERNAME: str = os.environ.get("CALDAV_USERNAME", "")
CALDAV_PASSWORD: str = os.environ.get("CALDAV_PASSWORD", "")

# ---------------------------------------------------------------------------
# FastMCP application
# ---------------------------------------------------------------------------

mcp = FastMCP("calendar")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_credentials() -> None:
    """Raise early if credentials are missing."""
    if not CALDAV_URL or not CALDAV_USERNAME or not CALDAV_PASSWORD:
        raise RuntimeError(
            "CALDAV_URL, CALDAV_USERNAME, and CALDAV_PASSWORD environment "
            "variables must all be set."
        )


def _connect() -> caldav.DAVClient:
    """Return an authenticated CalDAV client."""
    _require_credentials()
    client = caldav.DAVClient(
        url=CALDAV_URL,
        username=CALDAV_USERNAME,
        password=CALDAV_PASSWORD,
    )
    return client


def _get_principal() -> caldav.Principal:
    """Return the CalDAV principal (top-level account object)."""
    client = _connect()
    return client.principal()


def _find_calendar(principal: caldav.Principal, calendar_name: str) -> caldav.Calendar:
    """Find a calendar by name. Raises ValueError if not found."""
    calendars = principal.calendars()
    for cal in calendars:
        if cal.name and cal.name.lower() == calendar_name.lower():
            return cal
    available = [c.name for c in calendars if c.name]
    raise ValueError(
        f"Calendar '{calendar_name}' not found. "
        f"Available calendars: {available}"
    )


def _parse_dt(value) -> str:
    """Convert an icalendar datetime/date to ISO string."""
    if value is None:
        return ""
    dt = value.dt if hasattr(value, "dt") else value
    if isinstance(dt, datetime):
        return dt.isoformat()
    if isinstance(dt, date):
        return dt.isoformat()
    return str(dt)


def _parse_text(value) -> str:
    """Safely convert an icalendar text property to string."""
    if value is None:
        return ""
    return str(value)


def _parse_attendees(component) -> list[str]:
    """Extract attendee email addresses from a VEVENT component."""
    attendees = component.get("attendee")
    if attendees is None:
        return []
    if not isinstance(attendees, list):
        attendees = [attendees]
    result = []
    for a in attendees:
        addr = str(a)
        if addr.lower().startswith("mailto:"):
            addr = addr[7:]
        result.append(addr)
    return result


def _vevent_to_dict(component) -> dict:
    """Convert a VEVENT icalendar component to a clean dict."""
    return {
        "uid": _parse_text(component.get("uid")),
        "summary": _parse_text(component.get("summary")),
        "start": _parse_dt(component.get("dtstart")),
        "end": _parse_dt(component.get("dtend")),
        "location": _parse_text(component.get("location")),
        "description": _parse_text(component.get("description")),
        "status": _parse_text(component.get("status")),
        "organizer": _parse_text(component.get("organizer")),
        "attendees": _parse_attendees(component),
        "created": _parse_dt(component.get("created")),
        "last_modified": _parse_dt(component.get("last-modified")),
    }


def _extract_events(cal_objects) -> list[dict]:
    """Extract VEVENT data from a list of caldav calendar objects."""
    events = []
    for obj in cal_objects:
        try:
            ical = Calendar.from_ical(obj.data)
            for component in ical.walk():
                if component.name == "VEVENT":
                    events.append(_vevent_to_dict(component))
        except Exception:
            continue
    return events


def _parse_date_input(date_str: str) -> datetime:
    """Parse a date string in YYYY-MM-DD or ISO format to datetime."""
    date_str = date_str.strip()
    # Try full ISO datetime first
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Invalid date format: '{date_str}'. "
        f"Use YYYY-MM-DD or YYYY-MM-DDTHH:MM."
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def list_calendars() -> dict:
    """List all calendars on the connected CalDAV server.

    Returns:
        dict with "calendars" (list of name/url pairs) and "count".
    """
    try:
        principal = _get_principal()
        calendars = principal.calendars()
        result = []
        for cal in calendars:
            result.append({
                "name": cal.name or "(unnamed)",
                "url": str(cal.url),
            })
        return {"count": len(result), "calendars": result}
    except RuntimeError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Failed to list calendars: {exc}"}


@mcp.tool()
def list_events(
    calendar_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """List events from a calendar with optional date range filter.

    If no calendar_name is provided, lists events from all calendars.
    If no date range is provided, defaults to the next 30 days.

    Args:
        calendar_name: Name of the calendar to query (optional, searches all if omitted).
        start_date: Start of date range, YYYY-MM-DD or YYYY-MM-DDTHH:MM (default: today).
        end_date: End of date range, YYYY-MM-DD or YYYY-MM-DDTHH:MM (default: 30 days from start).

    Returns:
        dict with "events" (list) and "count".
    """
    try:
        principal = _get_principal()

        # Parse date range
        if start_date:
            dt_start = _parse_date_input(start_date)
        else:
            dt_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if end_date:
            dt_end = _parse_date_input(end_date)
        else:
            dt_end = dt_start + timedelta(days=30)

        # Determine which calendars to search
        if calendar_name:
            cals = [_find_calendar(principal, calendar_name)]
        else:
            cals = principal.calendars()

        all_events = []
        for cal in cals:
            try:
                results = cal.date_search(
                    start=dt_start,
                    end=dt_end,
                    expand=True,
                )
                events = _extract_events(results)
                for ev in events:
                    ev["calendar"] = cal.name or "(unnamed)"
                all_events.extend(events)
            except Exception as exc:
                all_events.append({
                    "calendar": cal.name or "(unnamed)",
                    "error": f"Failed to search: {exc}",
                })

        # Sort by start time
        def sort_key(e):
            return e.get("start", "") or ""
        all_events.sort(key=sort_key)

        return {"count": len(all_events), "events": all_events}
    except RuntimeError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Failed to list events: {exc}"}


@mcp.tool()
def get_event(calendar_name: str, event_uid: str) -> dict:
    """Get full details for a specific event by its UID.

    Args:
        calendar_name: Name of the calendar containing the event.
        event_uid: The unique identifier (UID) of the event.

    Returns:
        dict with full event details (summary, start, end, location,
        description, attendees, status, organizer).
    """
    try:
        principal = _get_principal()
        cal = _find_calendar(principal, calendar_name)

        event_obj = cal.event_by_uid(event_uid)
        ical = Calendar.from_ical(event_obj.data)

        for component in ical.walk():
            if component.name == "VEVENT":
                result = _vevent_to_dict(component)
                result["calendar"] = calendar_name
                result["raw_ical"] = event_obj.data
                return result

        return {"error": f"No VEVENT found in event UID '{event_uid}'."}
    except RuntimeError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}
    except caldav.error.NotFoundError:
        return {"error": f"Event UID '{event_uid}' not found in calendar '{calendar_name}'."}
    except Exception as exc:
        return {"error": f"Failed to get event: {exc}"}


@mcp.tool()
def create_event(
    calendar_name: str,
    summary: str,
    start: str,
    end: str,
    location: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """Create a new calendar event.

    Args:
        calendar_name: Name of the calendar to add the event to.
        summary: Event title / summary.
        start: Start datetime, YYYY-MM-DDTHH:MM (e.g. 2026-03-20T14:00).
        end: End datetime, YYYY-MM-DDTHH:MM (e.g. 2026-03-20T15:00).
        location: Event location (optional).
        description: Event description / notes (optional).

    Returns:
        dict with "success", "uid", and event details.
    """
    try:
        principal = _get_principal()
        cal = _find_calendar(principal, calendar_name)

        dt_start = _parse_date_input(start)
        dt_end = _parse_date_input(end)

        if dt_end <= dt_start:
            return {"error": "End time must be after start time."}

        # Build iCalendar VCALENDAR/VEVENT
        ical = Calendar()
        ical.add("prodid", "-//AgentPlatform//CalendarMCP//EN")
        ical.add("version", "2.0")

        event = Event()
        event.add("summary", summary)
        event.add("dtstart", dt_start)
        event.add("dtend", dt_end)
        event.add("dtstamp", datetime.now())

        if location:
            event.add("location", location)
        if description:
            event.add("description", description)

        ical.add_component(event)

        # Save to CalDAV server
        created = cal.save_event(ical.to_ical().decode("utf-8"))

        # Extract the UID from the created event
        uid = ""
        try:
            created_ical = Calendar.from_ical(created.data)
            for component in created_ical.walk():
                if component.name == "VEVENT":
                    uid = _parse_text(component.get("uid"))
                    break
        except Exception:
            uid = "(could not extract UID)"

        return {
            "success": True,
            "uid": uid,
            "summary": summary,
            "start": dt_start.isoformat(),
            "end": dt_end.isoformat(),
            "calendar": calendar_name,
            "location": location or "",
        }
    except RuntimeError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Failed to create event: {exc}"}


@mcp.tool()
def update_event(
    calendar_name: str,
    event_uid: str,
    summary: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
) -> dict:
    """Update an existing calendar event. Only provided fields are changed.

    Args:
        calendar_name: Name of the calendar containing the event.
        event_uid: The UID of the event to update.
        summary: New event title (optional).
        start: New start datetime, YYYY-MM-DDTHH:MM (optional).
        end: New end datetime, YYYY-MM-DDTHH:MM (optional).
        location: New location (optional).
        description: New description (optional).

    Returns:
        dict with "success" and updated event details.
    """
    try:
        principal = _get_principal()
        cal = _find_calendar(principal, calendar_name)

        event_obj = cal.event_by_uid(event_uid)
        ical = Calendar.from_ical(event_obj.data)

        updated = False
        for component in ical.walk():
            if component.name != "VEVENT":
                continue

            if summary is not None:
                if "summary" in component:
                    del component["summary"]
                component.add("summary", summary)
                updated = True

            if start is not None:
                dt_start = _parse_date_input(start)
                if "dtstart" in component:
                    del component["dtstart"]
                component.add("dtstart", dt_start)
                updated = True

            if end is not None:
                dt_end = _parse_date_input(end)
                if "dtend" in component:
                    del component["dtend"]
                component.add("dtend", dt_end)
                updated = True

            if location is not None:
                if "location" in component:
                    del component["location"]
                component.add("location", location)
                updated = True

            if description is not None:
                if "description" in component:
                    del component["description"]
                component.add("description", description)
                updated = True

            # Update last-modified timestamp
            if updated:
                if "last-modified" in component:
                    del component["last-modified"]
                component.add("last-modified", datetime.now())

        if not updated:
            return {"error": "No fields provided to update."}

        # Save updated event back to server
        event_obj.data = ical.to_ical().decode("utf-8")
        event_obj.save()

        return {
            "success": True,
            "uid": event_uid,
            "calendar": calendar_name,
            "fields_updated": [
                f for f in ["summary", "start", "end", "location", "description"]
                if locals().get(f) is not None
            ],
        }
    except RuntimeError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}
    except caldav.error.NotFoundError:
        return {"error": f"Event UID '{event_uid}' not found in calendar '{calendar_name}'."}
    except Exception as exc:
        return {"error": f"Failed to update event: {exc}"}


@mcp.tool()
def delete_event(calendar_name: str, event_uid: str) -> dict:
    """Delete a calendar event by its UID.

    Args:
        calendar_name: Name of the calendar containing the event.
        event_uid: The UID of the event to delete.

    Returns:
        dict with "success" and deleted event UID.
    """
    try:
        principal = _get_principal()
        cal = _find_calendar(principal, calendar_name)

        event_obj = cal.event_by_uid(event_uid)
        event_obj.delete()

        return {
            "success": True,
            "uid": event_uid,
            "calendar": calendar_name,
            "message": f"Event '{event_uid}' deleted from '{calendar_name}'.",
        }
    except RuntimeError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}
    except caldav.error.NotFoundError:
        return {"error": f"Event UID '{event_uid}' not found in calendar '{calendar_name}'."}
    except Exception as exc:
        return {"error": f"Failed to delete event: {exc}"}


@mcp.tool()
def check_availability(
    calendar_name: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Check free/busy times in a date range for a specific calendar.

    Retrieves all events in the range and computes busy slots and free gaps.

    Args:
        calendar_name: Name of the calendar to check.
        start_date: Start of range, YYYY-MM-DD or YYYY-MM-DDTHH:MM.
        end_date: End of range, YYYY-MM-DD or YYYY-MM-DDTHH:MM.

    Returns:
        dict with "busy_slots" (list of start/end/summary), "free_slots"
        (list of start/end), and summary stats.
    """
    try:
        principal = _get_principal()
        cal = _find_calendar(principal, calendar_name)

        dt_start = _parse_date_input(start_date)
        dt_end = _parse_date_input(end_date)

        if dt_end <= dt_start:
            return {"error": "End date must be after start date."}

        # Fetch events in range
        results = cal.date_search(
            start=dt_start,
            end=dt_end,
            expand=True,
        )
        events = _extract_events(results)

        # Build busy slots — sort by start time
        busy_slots = []
        for ev in events:
            ev_start = ev.get("start", "")
            ev_end = ev.get("end", "")
            if ev_start and ev_end:
                busy_slots.append({
                    "start": ev_start,
                    "end": ev_end,
                    "summary": ev.get("summary", "(no title)"),
                })

        busy_slots.sort(key=lambda x: x["start"])

        # Compute free slots between busy periods
        free_slots = []
        cursor = dt_start

        for slot in busy_slots:
            try:
                slot_start = _parse_date_input(slot["start"])
            except ValueError:
                continue
            if slot_start > cursor:
                free_slots.append({
                    "start": cursor.isoformat(),
                    "end": slot_start.isoformat(),
                })
            try:
                slot_end = _parse_date_input(slot["end"])
                if slot_end > cursor:
                    cursor = slot_end
            except ValueError:
                continue

        # Add trailing free slot if there's time left
        if cursor < dt_end:
            free_slots.append({
                "start": cursor.isoformat(),
                "end": dt_end.isoformat(),
            })

        # Calculate total busy/free hours
        total_hours = (dt_end - dt_start).total_seconds() / 3600
        busy_hours = 0
        for slot in busy_slots:
            try:
                s = _parse_date_input(slot["start"])
                e = _parse_date_input(slot["end"])
                busy_hours += (e - s).total_seconds() / 3600
            except ValueError:
                continue
        free_hours = total_hours - busy_hours

        return {
            "calendar": calendar_name,
            "range": {
                "start": dt_start.isoformat(),
                "end": dt_end.isoformat(),
            },
            "summary": {
                "total_hours": round(total_hours, 1),
                "busy_hours": round(busy_hours, 1),
                "free_hours": round(max(free_hours, 0), 1),
                "event_count": len(busy_slots),
            },
            "busy_slots": busy_slots,
            "free_slots": free_slots,
        }
    except RuntimeError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"Failed to check availability: {exc}"}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
