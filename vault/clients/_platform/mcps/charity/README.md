# Charity MCP Server

Nonprofit organization lookup and verification via the ProPublica Nonprofit Explorer API. Provides EIN lookup, name/location search, tax-deductible status verification, charity classification, and financial filing data for ~1.8M US tax-exempt organizations.

**Free API, no API key required.**

## Setup

### Environment Variables

None required. The ProPublica Nonprofit Explorer API is free and does not require authentication.

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Tools

| Tool | Description |
|------|-------------|
| lookup_ein | Look up a nonprofit by EIN — full profile, classification, and recent filings |
| search_charities | Search nonprofits by name, city, keywords — filter by state and NTEE category |
| verify_tax_deductible | Check if donations to an org are tax-deductible (501(c)(3) verification) |
| classify_charity | Get full IRS classification and NTEE category for a nonprofit |
| get_charity_financials | Get financial summary from Form 990 filings with revenue trend analysis |

## Data Source

[ProPublica Nonprofit Explorer API v2](https://projects.propublica.org/nonprofits/api) — covers all US tax-exempt organizations registered with the IRS. Filing data comes from electronically filed Form 990s.

**Coverage notes:**
- Organization identity, classification, and tax status: comprehensive (~1.8M orgs)
- Financial filing data: available for e-filers only (~30% of all nonprofits)
- Does NOT include: website URLs, phone numbers, email addresses, or contact names

## Registration

Add to `.mcp.json`:
```json
{
  "charity": {
    "type": "stdio",
    "command": "python3",
    "args": ["/path/to/vault/clients/_platform/mcps/charity/server.py"],
    "env": {}
  }
}
```
