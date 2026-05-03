# Google Search Console MCP Server

Search performance analytics, URL inspection, sitemap management, and site
property management via Google Search Console API v1.

## Setup

### 1. Google Cloud Project + OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select existing)
3. Enable the **Google Search Console API** (also called "Search Console API" or "Webmasters API")
4. Create credentials:
   - **Service Account** (recommended for server use): Download JSON key file
   - **OAuth 2.0 Client ID** (for user-level access): Download client secrets JSON
5. For service accounts: add the service account email as a user in Search Console with appropriate permissions

### 2. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| GSC_CREDENTIALS_FILE | Yes* | Path to service account JSON key file |
| GSC_OAUTH_CLIENT_FILE | Yes* | Path to OAuth 2.0 client secrets JSON (alternative to service account) |
| GSC_TOKEN_FILE | No | Path to store OAuth token (default: gsc_token.json) |

*One of GSC_CREDENTIALS_FILE or GSC_OAUTH_CLIENT_FILE must be set.

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Tools (13)

| Tool | Description |
|------|-------------|
| list_properties | List all Search Console properties the account has access to |
| get_search_analytics | Query search performance — clicks, impressions, CTR, position by dimensions |
| get_advanced_search_analytics | Advanced query with filtering, pagination, and data freshness control |
| compare_search_periods | Compare performance between two time periods with deltas |
| inspect_url | Check a URL's indexing status, crawl info, mobile usability, rich results |
| list_sitemaps | List all sitemaps for a property |
| get_sitemap | Get detailed info about a specific sitemap |
| submit_sitemap | Submit a sitemap to Google |
| delete_sitemap | Remove a sitemap from Search Console |
| get_site_details | Get property details and permission level |
| get_performance_overview | High-level performance overview with daily trend |
| get_top_pages | Top-performing pages by clicks |
| get_queries_for_page | Search queries driving traffic to a specific page |

## Registration

Add to `.mcp.json`:
```json
{
  "google-search-console": {
    "type": "stdio",
    "command": "python3",
    "args": ["vault/clients/_platform/mcps/google-search-console/server.py"],
    "env": {
      "GSC_CREDENTIALS_FILE": "/path/to/service-account-key.json"
    }
  }
}
```

## Credential Setup Guide

### Option A: Service Account (recommended for automation)

1. In Google Cloud Console, go to IAM & Admin > Service Accounts
2. Create a service account, download the JSON key
3. In Google Search Console, go to Settings > Users and permissions
4. Add the service account email (from the JSON) as an Owner or Full user
5. Set `GSC_CREDENTIALS_FILE` to the JSON key path

### Option B: OAuth 2.0 (for personal account access)

1. In Google Cloud Console, go to APIs & Services > Credentials
2. Create OAuth 2.0 Client ID (Desktop app type)
3. Download the client secrets JSON
4. Set `GSC_OAUTH_CLIENT_FILE` to the downloaded JSON path
5. On first run, a browser window opens for consent — the token is saved for reuse
