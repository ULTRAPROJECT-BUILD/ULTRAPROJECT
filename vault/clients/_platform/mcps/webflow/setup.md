---
type: mcp-config
name: webflow
status: waiting-credentials
transport: remote-sse
url: https://mcp.webflow.com/sse
auth: oauth
created: 2026-03-19T13:16
---

# Webflow MCP — Setup Guide

## Overview

Official Webflow MCP server. Remote SSE transport with OAuth authentication.
No local code to install — Webflow hosts the MCP server at `mcp.webflow.com`.

## What It Provides

**Data API tools (CMS + site management):**
- Sites: list sites, get site details, publish sites
- Pages: list/get/update pages, update page metadata and SEO
- CMS Collections: list/create/get/update/delete collections
- CMS Items: list/create/get/update/delete/publish collection items (bulk supported)
- Assets: list/upload/get/update/delete assets, manage asset folders
- Custom Code: register/list/apply custom code scripts
- Domains: list custom domains

**Designer API tools (live canvas manipulation, requires Bridge App):**
- Elements: create/modify sections, containers, grids, text, images
- Styles: create/apply CSS classes, manage responsive breakpoints
- Components: build reusable components, manage instances
- Variables: create/manage design variables and color schemes
- Typography: set font families, sizes, weights

## Prerequisites

1. A Webflow account (any plan — free plan gives 1 site)
2. Node.js 22.3.0+ on the local machine (for mcp-remote proxy) — VERIFIED: v25.6.1
3. Browser access for OAuth authorization flow

## Configuration for .mcp.json

Once admin authorizes OAuth, add to `.mcp.json`:

```json
"webflow": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "mcp-remote", "https://mcp.webflow.com/sse"]
}
```

**How it works:** `mcp-remote` is an npm package that proxies a remote SSE MCP
server into a local stdio transport. Claude Code connects to the local process,
which forwards requests to `mcp.webflow.com/sse` using cached OAuth tokens.

## Alternative: Local Install with API Token

If OAuth flow is impractical for headless operation, use a Webflow API token:

```json
"webflow": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "webflow-mcp-server@latest"],
  "env": {
    "WEBFLOW_TOKEN": "[WEBFLOW_API_TOKEN]"
  }
}
```

**To generate an API token:**
1. Go to https://developers.webflow.com/data/reference/rest-introduction
2. Log in to your Webflow account
3. Open the API Playground
4. Copy the bearer token from the Request Generator
5. Or: Create a Site API Token in Webflow site settings > Integrations

**Recommended for this platform:** The local install with API token is better
suited for scripted operation since it does not require
interactive browser-based OAuth refresh. The token approach also works headlessly.

## Admin Setup Steps

1. Create or log in to a Webflow account
2. Create at least one site (or use existing)
3. Generate an API token (site settings > Integrations > API Access)
4. Provide the token to set WEBFLOW_TOKEN in .mcp.json
5. Agent will then register the MCP and run integration tests

## Designer API (Optional, Advanced)

The Designer API tools require the Webflow MCP Bridge App to be open in the
Webflow Designer. This is useful for live canvas manipulation but NOT required
for CMS/data operations. The Bridge App installs automatically during OAuth.

For headless platform operation, Data API tools alone cover:
- CMS content management (collections, items, bulk updates)
- Page metadata and SEO
- Asset management
- Custom code injection
- Site publishing

## Security Notes

- Remote server: Webflow hosts, no local credential storage needed for OAuth mode
- API token mode: token stored in .mcp.json env vars (same pattern as other MCPs)
- OAuth scopes: read/write access to authorized sites only
- No filesystem access, no shell execution
- All API calls go through Webflow's authenticated endpoints
