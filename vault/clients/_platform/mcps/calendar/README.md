# Calendar MCP Server (CalDAV)

CalDAV-based calendar management — list calendars, list/create/update/delete events, check availability. Works with any CalDAV provider (Google Calendar, Apple iCloud, Fastmail, etc.) using app-specific passwords. No OAuth required.

## Setup

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| CALDAV_URL | Yes | CalDAV server URL (see provider examples below) |
| CALDAV_USERNAME | Yes | Account username or email address |
| CALDAV_PASSWORD | Yes | App-specific password (NOT your regular password) |

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Provider Setup

**Google Calendar:**
1. Enable 2-Step Verification on your Google account
2. Generate an app-specific password at https://myaccount.google.com/apppasswords
3. Use CalDAV URL: `https://apidata.googleusercontent.com/caldav/v2/`
4. Username: your full Google account address

**Apple iCloud:**
1. Enable Two-Factor Authentication on your Apple ID
2. Generate an app-specific password at https://appleid.apple.com/account/manage
3. Use CalDAV URL: `https://caldav.icloud.com/`
4. Username: your Apple ID email

**Fastmail:**
1. Generate an app password at Settings > Privacy & Security > Integrations
2. Use CalDAV URL: `https://caldav.fastmail.com/dav/calendars/user/{email}/`
3. Username: your Fastmail email address

**Any CalDAV Provider:**
- Provide the CalDAV server URL, username, and password/app-password
- Most providers document their CalDAV endpoint URL

## Tools

| Tool | Description |
|------|-------------|
| list_calendars | List all calendars on the connected CalDAV server |
| list_events | List events with optional calendar name and date range filter |
| get_event | Get full event details (summary, times, location, description, attendees) by UID |
| create_event | Create a new calendar event with summary, start/end, optional location and description |
| update_event | Update fields on an existing event (only provided fields change) |
| delete_event | Delete an event by UID |
| check_availability | Compute free/busy slots in a date range for a specific calendar |

## Registration

Add to `.mcp.json`:
```json
{
  "calendar": {
    "type": "stdio",
    "command": "python3",
    "args": ["vault/clients/_platform/mcps/calendar/server.py"],
    "env": {
      "CALDAV_URL": "",
      "CALDAV_USERNAME": "",
      "CALDAV_PASSWORD": ""
    }
  }
}
```
