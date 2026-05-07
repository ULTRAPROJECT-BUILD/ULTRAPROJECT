# Eventbrite MCP Server

Event management and marketing via Eventbrite API v3. List events, get event details, attendees, ticket classes, venues, and search within organization events.

## Setup

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| EVENTBRITE_API_TOKEN | Yes | Eventbrite private OAuth token (API key) |

### Get an API Token

1. Go to https://www.eventbrite.com/platform/api-keys
2. Log in with your Eventbrite account
3. Create a new API key or copy your existing private token
4. Set it as the `EVENTBRITE_API_TOKEN` environment variable

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Tools

| Tool | Description |
|------|-------------|
| list_events | List user's events with status filter (live, draft, ended, etc.) |
| get_event | Get full event details (name, description, dates, venue, tickets, organizer) |
| get_attendees | List attendees/orders for an event with status filter and pagination |
| get_ticket_classes | Get ticket types, pricing, availability, and sales status |
| get_venue | Get venue details (name, address, city, coordinates) |
| search_events | Search organization events by keyword, location, or date range |

## Important Notes

- Eventbrite deprecated the public Event Search API in February 2020. The `search_events` tool searches within the authenticated user's organization events only.
- All tools require a valid `EVENTBRITE_API_TOKEN`.
- Responses are paginated (50 items per page by default).

## Registration

Add to `.mcp.json`:
```json
{
  "eventbrite": {
    "type": "stdio",
    "command": "python3",
    "args": ["vault/clients/_platform/mcps/eventbrite/server.py"],
    "env": {
      "EVENTBRITE_API_TOKEN": ""
    }
  }
}
```
