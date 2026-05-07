"""
Google Search Console MCP Server
Search performance analytics, URL inspection, sitemap management, and site
property management via Google Search Console API v1.

Requires Google OAuth 2.0 credentials (service account or OAuth client).
Authentication uses google-auth + google-api-python-client.

Environment variables:
  GSC_CREDENTIALS_FILE — path to service account JSON key file
  GSC_OAUTH_CLIENT_FILE — path to OAuth 2.0 client secrets JSON (alternative)
  GSC_TOKEN_FILE — path to store/read OAuth token (default: gsc_token.json)
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("google-search-console")

# --- Configuration ---

GSC_CREDENTIALS_FILE = os.environ.get("GSC_CREDENTIALS_FILE", "")
GSC_OAUTH_CLIENT_FILE = os.environ.get("GSC_OAUTH_CLIENT_FILE", "")
GSC_TOKEN_FILE = os.environ.get("GSC_TOKEN_FILE", "gsc_token.json")

SCOPES = ["https://www.googleapis.com/auth/webmasters"]
TIMEOUT = 30  # seconds


def _get_service():
    """Build and return an authorized Google Search Console API service.

    Tries service account credentials first, then OAuth 2.0 client flow.
    Returns (service, None) on success or (None, error_string) on failure.
    """
    try:
        from googleapiclient.discovery import build

        # Method 1: Service account credentials
        if GSC_CREDENTIALS_FILE and os.path.exists(GSC_CREDENTIALS_FILE):
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(
                GSC_CREDENTIALS_FILE, scopes=SCOPES
            )
            service = build("searchconsole", "v1", credentials=creds)
            return service, None

        # Method 2: OAuth 2.0 with stored token
        if GSC_OAUTH_CLIENT_FILE and os.path.exists(GSC_OAUTH_CLIENT_FILE):
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request

            creds = None

            # Try loading existing token
            if os.path.exists(GSC_TOKEN_FILE):
                try:
                    creds = Credentials.from_authorized_user_file(
                        GSC_TOKEN_FILE, SCOPES
                    )
                except Exception:
                    creds = None

            # Refresh if expired
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None

            # Run OAuth flow if no valid credentials
            if not creds or not creds.valid:
                from google_auth_oauthlib.flow import InstalledAppFlow
                flow = InstalledAppFlow.from_client_secrets_file(
                    GSC_OAUTH_CLIENT_FILE, SCOPES
                )
                creds = flow.run_local_server(port=0)
                # Save token for next run
                with open(GSC_TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())

            service = build("searchconsole", "v1", credentials=creds)
            return service, None

        return None, (
            "Error: No credentials configured. Set GSC_CREDENTIALS_FILE "
            "(service account JSON) or GSC_OAUTH_CLIENT_FILE (OAuth client "
            "secrets JSON) environment variable."
        )

    except ImportError as e:
        return None, f"Error: Missing dependency — {str(e)}. Run: pip install -r requirements.txt"
    except Exception as e:
        return None, f"Error authenticating with Google: {str(e)}"


def _date_str(days_ago: int) -> str:
    """Return a date string N days ago in YYYY-MM-DD format."""
    return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


# --- Tool 1: List Properties ---

@mcp.tool()
def list_properties() -> str:
    """List all Search Console properties (websites) the authenticated account has access to.

    Returns:
        JSON list of properties with siteUrl and permissionLevel
    """
    service, err = _get_service()
    if err:
        return err
    try:
        result = service.sites().list().execute()
        sites = result.get("siteEntry", [])
        properties = []
        for site in sites:
            properties.append({
                "site_url": site.get("siteUrl"),
                "permission_level": site.get("permissionLevel"),
            })
        return json.dumps(properties, indent=2)
    except Exception as e:
        return f"Error listing properties: {str(e)}"


# --- Tool 2: Get Search Analytics ---

@mcp.tool()
def get_search_analytics(
    site_url: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 28,
    dimensions: str = "query",
    search_type: str = "web",
    row_limit: int = 25,
) -> str:
    """Query search performance data — clicks, impressions, CTR, and average position.

    This is the core analytics tool. Use it to understand which queries drive
    traffic, which pages perform best, and how performance varies by country/device.

    Args:
        site_url: The Search Console property URL (e.g., "https://example.com/" or "sc-domain:example.com")
        start_date: Start date in YYYY-MM-DD format (default: {days} days ago)
        end_date: End date in YYYY-MM-DD format (default: today)
        days: Number of days to look back if start_date not specified (default: 28)
        dimensions: Comma-separated dimensions — query, page, country, device, date (default: "query")
        search_type: Search type — web, image, video, news, googleNews, discover (default: "web")
        row_limit: Maximum rows to return, 1-25000 (default: 25)

    Returns:
        JSON with rows containing dimension keys and metrics (clicks, impressions, ctr, position)
    """
    service, err = _get_service()
    if err:
        return err
    try:
        if not start_date:
            start_date = _date_str(days)
        if not end_date:
            end_date = _date_str(0)

        dim_list = [d.strip() for d in dimensions.split(",")]
        row_limit = max(1, min(row_limit, 25000))

        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dim_list,
            "type": search_type,
            "rowLimit": row_limit,
        }

        result = service.searchAnalytics().query(
            siteUrl=site_url, body=body
        ).execute()

        rows = result.get("rows", [])
        output = []
        for row in rows:
            entry = {}
            keys = row.get("keys", [])
            for i, dim in enumerate(dim_list):
                entry[dim] = keys[i] if i < len(keys) else ""
            entry["clicks"] = row.get("clicks", 0)
            entry["impressions"] = row.get("impressions", 0)
            entry["ctr"] = round(row.get("ctr", 0), 4)
            entry["position"] = round(row.get("position", 0), 1)
            output.append(entry)

        return json.dumps({
            "site_url": site_url,
            "start_date": start_date,
            "end_date": end_date,
            "dimensions": dim_list,
            "search_type": search_type,
            "row_count": len(output),
            "rows": output,
        }, indent=2)
    except Exception as e:
        return f"Error querying search analytics: {str(e)}"


# --- Tool 3: Advanced Search Analytics ---

@mcp.tool()
def get_advanced_search_analytics(
    site_url: str,
    start_date: str,
    end_date: str,
    dimensions: str = "query",
    search_type: str = "web",
    row_limit: int = 100,
    start_row: int = 0,
    filter_dimension: Optional[str] = None,
    filter_operator: str = "contains",
    filter_expression: Optional[str] = None,
    data_state: str = "final",
) -> str:
    """Advanced search analytics query with filtering, pagination, and data freshness control.

    Use this for targeted analysis — filter by specific query patterns, pages,
    countries, or devices. Supports pagination for large result sets.

    Args:
        site_url: The Search Console property URL
        start_date: Start date in YYYY-MM-DD format (required)
        end_date: End date in YYYY-MM-DD format (required)
        dimensions: Comma-separated dimensions — query, page, country, device, date (default: "query")
        search_type: Search type — web, image, video, news, googleNews, discover (default: "web")
        row_limit: Rows per page, 1-25000 (default: 100)
        start_row: Pagination offset (default: 0)
        filter_dimension: Dimension to filter on — query, page, country, device (optional)
        filter_operator: Filter operator — contains, equals, notContains, notEquals, includingRegex, excludingRegex (default: "contains")
        filter_expression: Filter value to match (required if filter_dimension is set)
        data_state: Data freshness — "final" (stable) or "all" (includes fresh/partial data) (default: "final")

    Returns:
        JSON with filtered/paginated rows and metadata
    """
    service, err = _get_service()
    if err:
        return err
    try:
        dim_list = [d.strip() for d in dimensions.split(",")]
        row_limit = max(1, min(row_limit, 25000))

        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dim_list,
            "type": search_type,
            "rowLimit": row_limit,
            "startRow": start_row,
            "dataState": data_state,
        }

        # Add dimension filter if specified
        if filter_dimension and filter_expression:
            operator_map = {
                "contains": "contains",
                "equals": "equals",
                "notContains": "notContains",
                "notEquals": "notEquals",
                "includingRegex": "includingRegex",
                "excludingRegex": "excludingRegex",
            }
            op = operator_map.get(filter_operator, "contains")
            body["dimensionFilterGroups"] = [{
                "filters": [{
                    "dimension": filter_dimension,
                    "operator": op,
                    "expression": filter_expression,
                }]
            }]

        result = service.searchAnalytics().query(
            siteUrl=site_url, body=body
        ).execute()

        rows = result.get("rows", [])
        output = []
        for row in rows:
            entry = {}
            keys = row.get("keys", [])
            for i, dim in enumerate(dim_list):
                entry[dim] = keys[i] if i < len(keys) else ""
            entry["clicks"] = row.get("clicks", 0)
            entry["impressions"] = row.get("impressions", 0)
            entry["ctr"] = round(row.get("ctr", 0), 4)
            entry["position"] = round(row.get("position", 0), 1)
            output.append(entry)

        return json.dumps({
            "site_url": site_url,
            "start_date": start_date,
            "end_date": end_date,
            "dimensions": dim_list,
            "search_type": search_type,
            "data_state": data_state,
            "start_row": start_row,
            "row_count": len(output),
            "rows": output,
        }, indent=2)
    except Exception as e:
        return f"Error querying advanced search analytics: {str(e)}"


# --- Tool 4: Compare Search Periods ---

@mcp.tool()
def compare_search_periods(
    site_url: str,
    period1_start: str,
    period1_end: str,
    period2_start: str,
    period2_end: str,
    dimensions: str = "query",
    row_limit: int = 25,
) -> str:
    """Compare search performance between two time periods.

    Useful for measuring impact of SEO changes, seasonal trends, or before/after analysis.

    Args:
        site_url: The Search Console property URL
        period1_start: First period start date (YYYY-MM-DD) — typically the earlier/"before" period
        period1_end: First period end date (YYYY-MM-DD)
        period2_start: Second period start date (YYYY-MM-DD) — typically the later/"after" period
        period2_end: Second period end date (YYYY-MM-DD)
        dimensions: Comma-separated dimensions (default: "query")
        row_limit: Max rows per period (default: 25)

    Returns:
        JSON with side-by-side metrics and deltas for each dimension key
    """
    service, err = _get_service()
    if err:
        return err
    try:
        dim_list = [d.strip() for d in dimensions.split(",")]
        row_limit = max(1, min(row_limit, 25000))

        def _query_period(start: str, end: str) -> dict:
            body = {
                "startDate": start,
                "endDate": end,
                "dimensions": dim_list,
                "rowLimit": row_limit,
            }
            result = service.searchAnalytics().query(
                siteUrl=site_url, body=body
            ).execute()
            data = {}
            for row in result.get("rows", []):
                key = "|".join(row.get("keys", []))
                data[key] = {
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": round(row.get("ctr", 0), 4),
                    "position": round(row.get("position", 0), 1),
                }
            return data

        p1_data = _query_period(period1_start, period1_end)
        p2_data = _query_period(period2_start, period2_end)

        # Merge keys from both periods
        all_keys = set(list(p1_data.keys()) + list(p2_data.keys()))
        comparisons = []
        for key in sorted(all_keys):
            p1 = p1_data.get(key, {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0})
            p2 = p2_data.get(key, {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0})

            keys_split = key.split("|")
            entry = {}
            for i, dim in enumerate(dim_list):
                entry[dim] = keys_split[i] if i < len(keys_split) else ""

            entry["period1_clicks"] = p1["clicks"]
            entry["period2_clicks"] = p2["clicks"]
            entry["clicks_delta"] = p2["clicks"] - p1["clicks"]
            entry["period1_impressions"] = p1["impressions"]
            entry["period2_impressions"] = p2["impressions"]
            entry["impressions_delta"] = p2["impressions"] - p1["impressions"]
            entry["period1_ctr"] = p1["ctr"]
            entry["period2_ctr"] = p2["ctr"]
            entry["ctr_delta"] = round(p2["ctr"] - p1["ctr"], 4)
            entry["period1_position"] = p1["position"]
            entry["period2_position"] = p2["position"]
            # Lower position = better ranking, so negative delta = improvement
            entry["position_delta"] = round(p2["position"] - p1["position"], 1)

            comparisons.append(entry)

        # Sort by clicks_delta descending (biggest improvements first)
        comparisons.sort(key=lambda x: x["clicks_delta"], reverse=True)

        return json.dumps({
            "site_url": site_url,
            "period1": f"{period1_start} to {period1_end}",
            "period2": f"{period2_start} to {period2_end}",
            "dimensions": dim_list,
            "comparison_count": len(comparisons),
            "comparisons": comparisons,
        }, indent=2)
    except Exception as e:
        return f"Error comparing search periods: {str(e)}"


# --- Tool 5: Inspect URL ---

@mcp.tool()
def inspect_url(site_url: str, page_url: str, language_code: str = "en") -> str:
    """Inspect a URL's indexing status in Google Search.

    Returns coverage state, indexing verdict, crawl details, rich results,
    and mobile usability information.

    Args:
        site_url: The Search Console property URL
        page_url: The full URL to inspect (must be within the property)
        language_code: Language code for results (default: "en")

    Returns:
        JSON with indexing status, coverage state, crawl info, and rich results
    """
    service, err = _get_service()
    if err:
        return err
    try:
        body = {
            "inspectionUrl": page_url,
            "siteUrl": site_url,
            "languageCode": language_code,
        }
        result = service.urlInspection().index().inspect(body=body).execute()

        inspection = result.get("inspectionResult", {})
        index_status = inspection.get("indexStatusResult", {})
        mobile = inspection.get("mobileUsabilityResult", {})
        rich_results = inspection.get("richResultsResult", {})

        output = {
            "page_url": page_url,
            "inspection_url": inspection.get("inspectionResultLink"),
            "index_status": {
                "verdict": index_status.get("verdict"),
                "coverage_state": index_status.get("coverageState"),
                "robotstxt_state": index_status.get("robotsTxtState"),
                "indexing_state": index_status.get("indexingState"),
                "last_crawl_time": index_status.get("lastCrawlTime"),
                "page_fetch_state": index_status.get("pageFetchState"),
                "google_canonical": index_status.get("googleCanonical"),
                "user_canonical": index_status.get("userCanonical"),
                "crawled_as": index_status.get("crawledAs"),
                "referring_urls": index_status.get("referringUrls", []),
            },
            "mobile_usability": {
                "verdict": mobile.get("verdict"),
                "issues": [
                    {"issue_type": i.get("issueType"), "severity": i.get("severity"), "message": i.get("message")}
                    for i in mobile.get("issues", [])
                ],
            },
            "rich_results": {
                "verdict": rich_results.get("verdict"),
                "detected_items": [
                    {
                        "rich_result_type": item.get("richResultType"),
                        "items": [
                            {"name": ri.get("name"), "issues": ri.get("issues", [])}
                            for ri in item.get("items", [])
                        ],
                    }
                    for item in rich_results.get("detectedItems", [])
                ],
            },
        }
        return json.dumps(output, indent=2)
    except Exception as e:
        return f"Error inspecting URL: {str(e)}"


# --- Tool 6: List Sitemaps ---

@mcp.tool()
def list_sitemaps(site_url: str) -> str:
    """List all sitemaps submitted for a Search Console property.

    Args:
        site_url: The Search Console property URL

    Returns:
        JSON list of sitemaps with path, type, status, and index counts
    """
    service, err = _get_service()
    if err:
        return err
    try:
        result = service.sitemaps().list(siteUrl=site_url).execute()
        sitemaps = result.get("sitemap", [])
        output = []
        for sm in sitemaps:
            contents = sm.get("contents", [])
            content_summary = []
            for c in contents:
                content_summary.append({
                    "type": c.get("type"),
                    "submitted": c.get("submitted"),
                    "indexed": c.get("indexed"),
                })
            output.append({
                "path": sm.get("path"),
                "type": sm.get("type"),
                "last_submitted": sm.get("lastSubmitted"),
                "last_downloaded": sm.get("lastDownloaded"),
                "is_pending": sm.get("isPending"),
                "warnings": sm.get("warnings"),
                "errors": sm.get("errors"),
                "contents": content_summary,
            })
        return json.dumps({
            "site_url": site_url,
            "sitemap_count": len(output),
            "sitemaps": output,
        }, indent=2)
    except Exception as e:
        return f"Error listing sitemaps: {str(e)}"


# --- Tool 7: Get Sitemap Details ---

@mcp.tool()
def get_sitemap(site_url: str, sitemap_url: str) -> str:
    """Get detailed information about a specific sitemap.

    Args:
        site_url: The Search Console property URL
        sitemap_url: The full URL of the sitemap (e.g., "https://example.com/sitemap.xml")

    Returns:
        JSON with sitemap details including content types, counts, and status
    """
    service, err = _get_service()
    if err:
        return err
    try:
        result = service.sitemaps().get(
            siteUrl=site_url, feedpath=sitemap_url
        ).execute()

        contents = []
        for c in result.get("contents", []):
            contents.append({
                "type": c.get("type"),
                "submitted": c.get("submitted"),
                "indexed": c.get("indexed"),
            })

        output = {
            "path": result.get("path"),
            "type": result.get("type"),
            "last_submitted": result.get("lastSubmitted"),
            "last_downloaded": result.get("lastDownloaded"),
            "is_pending": result.get("isPending"),
            "is_sitemaps_index": result.get("isSitemapsIndex"),
            "warnings": result.get("warnings"),
            "errors": result.get("errors"),
            "contents": contents,
        }
        return json.dumps(output, indent=2)
    except Exception as e:
        return f"Error getting sitemap details: {str(e)}"


# --- Tool 8: Submit Sitemap ---

@mcp.tool()
def submit_sitemap(site_url: str, sitemap_url: str) -> str:
    """Submit a sitemap to Google Search Console for the given property.

    Args:
        site_url: The Search Console property URL
        sitemap_url: The full URL of the sitemap to submit (e.g., "https://example.com/sitemap.xml")

    Returns:
        Confirmation message or error
    """
    service, err = _get_service()
    if err:
        return err
    try:
        service.sitemaps().submit(
            siteUrl=site_url, feedpath=sitemap_url
        ).execute()
        return json.dumps({
            "status": "submitted",
            "site_url": site_url,
            "sitemap_url": sitemap_url,
        }, indent=2)
    except Exception as e:
        return f"Error submitting sitemap: {str(e)}"


# --- Tool 9: Delete Sitemap ---

@mcp.tool()
def delete_sitemap(site_url: str, sitemap_url: str) -> str:
    """Remove a sitemap from Google Search Console.

    Args:
        site_url: The Search Console property URL
        sitemap_url: The full URL of the sitemap to delete

    Returns:
        Confirmation message or error
    """
    service, err = _get_service()
    if err:
        return err
    try:
        service.sitemaps().delete(
            siteUrl=site_url, feedpath=sitemap_url
        ).execute()
        return json.dumps({
            "status": "deleted",
            "site_url": site_url,
            "sitemap_url": sitemap_url,
        }, indent=2)
    except Exception as e:
        return f"Error deleting sitemap: {str(e)}"


# --- Tool 10: Get Site Details ---

@mcp.tool()
def get_site_details(site_url: str) -> str:
    """Get details about a Search Console property including permission level.

    Args:
        site_url: The Search Console property URL

    Returns:
        JSON with site URL and permission level
    """
    service, err = _get_service()
    if err:
        return err
    try:
        result = service.sites().get(siteUrl=site_url).execute()
        return json.dumps({
            "site_url": result.get("siteUrl"),
            "permission_level": result.get("permissionLevel"),
        }, indent=2)
    except Exception as e:
        return f"Error getting site details: {str(e)}"


# --- Tool 11: Performance Overview ---

@mcp.tool()
def get_performance_overview(site_url: str, days: int = 28) -> str:
    """Get a high-level performance overview with daily trends.

    Returns total clicks, impressions, CTR, and position plus daily breakdowns.
    Good for a quick health check of a site's search performance.

    Args:
        site_url: The Search Console property URL
        days: Number of days to look back (default: 28)

    Returns:
        JSON with totals and daily trend data
    """
    service, err = _get_service()
    if err:
        return err
    try:
        start = _date_str(days)
        end = _date_str(0)

        # Get totals (no dimensions)
        totals_body = {
            "startDate": start,
            "endDate": end,
        }
        totals_result = service.searchAnalytics().query(
            siteUrl=site_url, body=totals_body
        ).execute()

        totals_rows = totals_result.get("rows", [])
        total_clicks = 0
        total_impressions = 0
        avg_ctr = 0.0
        avg_position = 0.0
        if totals_rows:
            r = totals_rows[0]
            total_clicks = r.get("clicks", 0)
            total_impressions = r.get("impressions", 0)
            avg_ctr = round(r.get("ctr", 0), 4)
            avg_position = round(r.get("position", 0), 1)

        # Get daily breakdown
        daily_body = {
            "startDate": start,
            "endDate": end,
            "dimensions": ["date"],
            "rowLimit": days + 1,
        }
        daily_result = service.searchAnalytics().query(
            siteUrl=site_url, body=daily_body
        ).execute()

        daily_rows = []
        for row in daily_result.get("rows", []):
            keys = row.get("keys", [])
            daily_rows.append({
                "date": keys[0] if keys else "",
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0), 4),
                "position": round(row.get("position", 0), 1),
            })

        return json.dumps({
            "site_url": site_url,
            "period": f"{start} to {end}",
            "totals": {
                "clicks": total_clicks,
                "impressions": total_impressions,
                "ctr": avg_ctr,
                "average_position": avg_position,
            },
            "daily_trend": daily_rows,
        }, indent=2)
    except Exception as e:
        return f"Error getting performance overview: {str(e)}"


# --- Tool 12: Top Pages ---

@mcp.tool()
def get_top_pages(
    site_url: str,
    days: int = 28,
    row_limit: int = 25,
) -> str:
    """Get the top-performing pages by clicks.

    Args:
        site_url: The Search Console property URL
        days: Number of days to look back (default: 28)
        row_limit: Maximum pages to return (default: 25)

    Returns:
        JSON list of top pages with clicks, impressions, CTR, and position
    """
    service, err = _get_service()
    if err:
        return err
    try:
        body = {
            "startDate": _date_str(days),
            "endDate": _date_str(0),
            "dimensions": ["page"],
            "rowLimit": max(1, min(row_limit, 25000)),
        }
        result = service.searchAnalytics().query(
            siteUrl=site_url, body=body
        ).execute()

        pages = []
        for row in result.get("rows", []):
            keys = row.get("keys", [])
            pages.append({
                "page": keys[0] if keys else "",
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0), 4),
                "position": round(row.get("position", 0), 1),
            })

        return json.dumps({
            "site_url": site_url,
            "days": days,
            "page_count": len(pages),
            "pages": pages,
        }, indent=2)
    except Exception as e:
        return f"Error getting top pages: {str(e)}"


# --- Tool 13: Queries for Page ---

@mcp.tool()
def get_queries_for_page(
    site_url: str,
    page_url: str,
    days: int = 28,
    row_limit: int = 25,
) -> str:
    """Get the search queries that drive traffic to a specific page.

    Useful for understanding which keywords a page ranks for and identifying
    optimization opportunities.

    Args:
        site_url: The Search Console property URL
        page_url: The full URL of the page to analyze
        days: Number of days to look back (default: 28)
        row_limit: Maximum queries to return (default: 25)

    Returns:
        JSON list of queries with clicks, impressions, CTR, and position
    """
    service, err = _get_service()
    if err:
        return err
    try:
        body = {
            "startDate": _date_str(days),
            "endDate": _date_str(0),
            "dimensions": ["query"],
            "rowLimit": max(1, min(row_limit, 25000)),
            "dimensionFilterGroups": [{
                "filters": [{
                    "dimension": "page",
                    "operator": "equals",
                    "expression": page_url,
                }]
            }],
        }
        result = service.searchAnalytics().query(
            siteUrl=site_url, body=body
        ).execute()

        queries = []
        for row in result.get("rows", []):
            keys = row.get("keys", [])
            queries.append({
                "query": keys[0] if keys else "",
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0), 4),
                "position": round(row.get("position", 0), 1),
            })

        return json.dumps({
            "site_url": site_url,
            "page_url": page_url,
            "days": days,
            "query_count": len(queries),
            "queries": queries,
        }, indent=2)
    except Exception as e:
        return f"Error getting queries for page: {str(e)}"


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
