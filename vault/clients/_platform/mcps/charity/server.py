"""
Charity MCP Server — Nonprofit Organization Lookup & Verification

Provides real-time nonprofit lookup by EIN or name, tax-deductible status
verification, charity classification, and financial filing data via the
ProPublica Nonprofit Explorer API. Free, no API key required.
"""

import json
import urllib.request
import urllib.parse
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("charity")

# --- Configuration ---

BASE_URL = "https://projects.propublica.org/nonprofits/api/v2"

# NTEE Major Group codes for human-readable classification
NTEE_MAJOR_GROUPS = {
    "A": "Arts, Culture & Humanities",
    "B": "Education",
    "C": "Environment",
    "D": "Animal-Related",
    "E": "Health Care",
    "F": "Mental Health & Crisis Intervention",
    "G": "Voluntary Health Associations & Medical Disciplines",
    "H": "Medical Research",
    "I": "Crime & Legal-Related",
    "J": "Employment",
    "K": "Food, Agriculture & Nutrition",
    "L": "Housing & Shelter",
    "M": "Public Safety, Disaster Preparedness & Relief",
    "N": "Recreation & Sports",
    "O": "Youth Development",
    "P": "Human Services",
    "Q": "International, Foreign Affairs & National Security",
    "R": "Civil Rights, Social Action & Advocacy",
    "S": "Community Improvement & Capacity Building",
    "T": "Philanthropy, Voluntarism & Grantmaking Foundations",
    "U": "Science & Technology",
    "V": "Social Science",
    "W": "Public & Societal Benefit",
    "X": "Religion-Related",
    "Y": "Mutual & Membership Benefit",
    "Z": "Unknown",
}

# IRS subsection codes for tax-exempt status classification
SUBSECTION_CODES = {
    "03": "501(c)(3) — Charitable, Religious, Educational, Scientific",
    "04": "501(c)(4) — Social Welfare",
    "05": "501(c)(5) — Labor, Agricultural, Horticultural",
    "06": "501(c)(6) — Business Leagues, Chambers of Commerce",
    "07": "501(c)(7) — Social & Recreational Clubs",
    "08": "501(c)(8) — Fraternal Beneficiary Societies",
    "09": "501(c)(9) — Voluntary Employees' Beneficiary Associations",
    "10": "501(c)(10) — Domestic Fraternal Societies",
    "11": "501(c)(11) — Teachers' Retirement Fund Associations",
    "12": "501(c)(12) — Benevolent Life Insurance Associations",
    "13": "501(c)(13) — Cemetery Companies",
    "14": "501(c)(14) — State-Chartered Credit Unions",
    "15": "501(c)(15) — Mutual Insurance Companies",
    "19": "501(c)(19) — Veterans' Organizations",
    "23": "501(c)(23) — Veterans' Associations (pre-1880)",
    "25": "501(c)(25) — Real Property Title Holding Corporations",
    "27": "501(c)(27) — State-Sponsored Workers' Compensation",
    "40": "501(d) — Religious & Apostolic Organizations",
    "50": "501(e) — Cooperative Hospital Service Organizations",
    "60": "501(f) — Cooperative Service Organizations of Operating Education Organizations",
    "70": "501(k) — Child Care Organizations",
    "71": "501(n) — Charitable Risk Pools",
    "81": "4947(a)(1) — Private Foundations (non-exempt charitable trusts)",
    "92": "4947(a)(2) — Split-Interest Trusts",
}


# --- Helpers ---

def _fetch_json(url: str) -> dict[str, Any]:
    """Fetch JSON from a URL using stdlib only."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "charity-mcp-server/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fmt_currency(value: Any) -> str | None:
    """Format a dollar amount into a human-readable string."""
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if abs(num) >= 1_000_000_000:
        return f"${num / 1_000_000_000:.2f}B"
    if abs(num) >= 1_000_000:
        return f"${num / 1_000_000:.2f}M"
    if abs(num) >= 1_000:
        return f"${num / 1_000:.1f}K"
    return f"${num:,.0f}"


def _clean_ein(ein: str) -> str:
    """Normalize an EIN — strip dashes and whitespace."""
    return ein.replace("-", "").replace(" ", "").strip()


def _lookup_subsection(code: str) -> str:
    """Look up a subsection code, handling both padded and unpadded forms."""
    if not code:
        return "Unknown"
    return (
        SUBSECTION_CODES.get(code)
        or SUBSECTION_CODES.get(code.zfill(2))
        or f"501(c)({code})"
    )


def _classify_ntee(ntee_code: str | None) -> dict[str, str | None]:
    """Parse an NTEE code into major group and description."""
    if not ntee_code:
        return {"ntee_code": None, "major_group": None, "major_group_name": None}
    major = ntee_code[0].upper() if ntee_code else None
    return {
        "ntee_code": ntee_code,
        "major_group": major,
        "major_group_name": NTEE_MAJOR_GROUPS.get(major, "Unknown") if major else None,
    }


def _format_org_summary(org: dict[str, Any]) -> dict[str, Any]:
    """Format a ProPublica organization search result into a clean summary."""
    ein = str(org.get("ein", ""))
    formatted_ein = f"{ein[:2]}-{ein[2:]}" if len(ein) == 9 else ein
    ntee = _classify_ntee(org.get("ntee_code"))
    subsection = str(org.get("subsection_code", ""))

    return {
        "ein": formatted_ein,
        "name": org.get("name"),
        "city": org.get("city"),
        "state": org.get("state"),
        "zipcode": org.get("zipcode"),
        "ntee_code": ntee["ntee_code"],
        "classification": ntee["major_group_name"],
        "subsection": _lookup_subsection(subsection) if subsection else None,
        "tax_deductible": subsection == "03",
    }


def _format_filing(filing: dict[str, Any]) -> dict[str, Any]:
    """Format a single Form 990 filing into a clean summary."""
    total_revenue = filing.get("totrevenue")
    total_expenses = filing.get("totfuncexpns")
    total_assets = filing.get("totassetsend")
    total_liabilities = filing.get("totliabend")

    return {
        "tax_period": filing.get("tax_prd_yr"),
        "form_type": filing.get("formtype"),
        "total_revenue": total_revenue,
        "total_revenue_fmt": _fmt_currency(total_revenue),
        "total_expenses": total_expenses,
        "total_expenses_fmt": _fmt_currency(total_expenses),
        "total_assets": total_assets,
        "total_assets_fmt": _fmt_currency(total_assets),
        "total_liabilities": total_liabilities,
        "total_liabilities_fmt": _fmt_currency(total_liabilities),
        "net_income": (total_revenue - total_expenses) if total_revenue is not None and total_expenses is not None else None,
        "net_income_fmt": _fmt_currency((total_revenue - total_expenses)) if total_revenue is not None and total_expenses is not None else None,
        "pdf_url": filing.get("pdf_url"),
    }


# --- Tools ---

@mcp.tool()
def lookup_ein(ein: str) -> str:
    """Look up a nonprofit organization by EIN (Employer Identification Number).

    Returns the organization's full profile including name, address, tax-exempt
    classification, NTEE category, tax-deductible status, and recent Form 990
    financial filings (revenue, expenses, assets, liabilities).

    Args:
        ein: The 9-digit EIN (e.g. "13-1837418" or "131837418").

    Returns:
        JSON with organization details and filing history.
    """
    clean = _clean_ein(ein)
    if not clean.isdigit() or len(clean) != 9:
        return json.dumps({"error": f"Invalid EIN '{ein}'. Must be 9 digits (e.g. '13-1837418')."})

    try:
        url = f"{BASE_URL}/organizations/{clean}.json"
        data = _fetch_json(url)

        org = data.get("organization", {})
        filings_list = data.get("filings_with_data", [])
        filings_no_data = data.get("filings_without_data", [])

        formatted_ein = f"{clean[:2]}-{clean[2:]}"
        ntee = _classify_ntee(org.get("ntee_code"))
        subsection = str(org.get("subseccd", org.get("subsection_code", "")))

        result = {
            "ein": formatted_ein,
            "name": org.get("name"),
            "city": org.get("city"),
            "state": org.get("state"),
            "zipcode": org.get("zipcode"),
            "ntee_code": ntee["ntee_code"],
            "classification": ntee["major_group_name"],
            "subsection_code": subsection,
            "subsection_description": _lookup_subsection(subsection) if subsection else None,
            "tax_deductible": subsection == "03" or subsection == "3",
            "ruling_date": org.get("ruling_date"),
            "tax_period": org.get("tax_prd"),
            "asset_amount": org.get("asset_amt"),
            "asset_amount_fmt": _fmt_currency(org.get("asset_amt")),
            "income_amount": org.get("income_amt"),
            "income_amount_fmt": _fmt_currency(org.get("income_amt")),
            "revenue_amount": org.get("revenue_amt"),
            "revenue_amount_fmt": _fmt_currency(org.get("revenue_amt")),
            "filings_count": len(filings_list),
            "filings_without_data_count": len(filings_no_data),
            "recent_filings": [_format_filing(f) for f in filings_list[:5]],
        }
        return json.dumps(result, indent=2)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return json.dumps({"error": f"No organization found for EIN '{formatted_ein}'."})
        return json.dumps({"error": f"HTTP error {e.code} looking up EIN '{ein}': {e.reason}"})
    except Exception as e:
        return json.dumps({"error": f"Failed to look up EIN '{ein}': {e}"})


@mcp.tool()
def search_charities(
    query: str,
    state: str = "",
    ntee_category: int = 0,
    page: int = 0,
) -> str:
    """Search for nonprofit organizations by name, city, or keywords.

    Supports filtering by state and NTEE category. Returns paginated results
    with name, EIN, location, classification, and tax-deductible status.

    Args:
        query: Search terms — organization name, city, or keywords.
               Supports "+" for required terms, "-" for exclusions,
               quotes for exact phrases.
        state: Two-letter state code to filter (e.g. "TX", "CA"). Optional.
        ntee_category: NTEE major category number (1-10). Optional.
                       1=Arts, 2=Education, 3=Environment, 4=Health,
                       5=Human Services, 6=International, 7=Public Benefit,
                       8=Religion, 9=Mutual/Membership, 10=Unknown.
        page: Zero-indexed page number for pagination (default 0).

    Returns:
        JSON with total count and list of matching organizations.
    """
    if not query.strip():
        return json.dumps({"error": "Search query is required."})

    try:
        params: dict[str, str] = {"q": query.strip()}
        if state:
            params["state[id]"] = state.strip().upper()
        if ntee_category > 0:
            params["ntee[id]"] = str(ntee_category)
        if page > 0:
            params["page"] = str(page)

        url = f"{BASE_URL}/search.json?{urllib.parse.urlencode(params)}"
        data = _fetch_json(url)

        total = data.get("total_results", 0)
        orgs = data.get("organizations", [])

        results = [_format_org_summary(org) for org in orgs]

        output = {
            "query": query,
            "filters": {
                "state": state.upper() if state else "all",
                "ntee_category": ntee_category if ntee_category > 0 else "all",
            },
            "total_results": total,
            "page": page,
            "results_on_page": len(results),
            "organizations": results,
        }
        return json.dumps(output, indent=2)

    except Exception as e:
        return json.dumps({"error": f"Search failed for '{query}': {e}"})


@mcp.tool()
def verify_tax_deductible(ein: str) -> str:
    """Verify whether donations to a nonprofit are tax-deductible.

    Checks the organization's IRS subsection code. Only 501(c)(3)
    organizations qualify for tax-deductible charitable contributions.
    Returns the organization's name, status, and explanation.

    Args:
        ein: The 9-digit EIN (e.g. "13-1837418" or "131837418").

    Returns:
        JSON with tax-deductible status, explanation, and organization details.
    """
    clean = _clean_ein(ein)
    if not clean.isdigit() or len(clean) != 9:
        return json.dumps({"error": f"Invalid EIN '{ein}'. Must be 9 digits."})

    formatted_ein = f"{clean[:2]}-{clean[2:]}"
    try:
        url = f"{BASE_URL}/organizations/{clean}.json"
        data = _fetch_json(url)

        org = data.get("organization", {})
        subsection = str(org.get("subseccd", org.get("subsection_code", "")))
        is_deductible = subsection in ("03", "3")

        if is_deductible:
            explanation = (
                "This organization is classified under IRS Section 501(c)(3). "
                "Donations are generally tax-deductible as charitable contributions. "
                "Consult a tax advisor for your specific situation."
            )
        else:
            sub_desc = _lookup_subsection(subsection)
            explanation = (
                f"This organization is classified under IRS Section {sub_desc}. "
                "Donations to this type of organization are generally NOT "
                "tax-deductible as charitable contributions."
            )

        result = {
            "ein": formatted_ein,
            "name": org.get("name"),
            "city": org.get("city"),
            "state": org.get("state"),
            "subsection_code": subsection,
            "subsection_description": _lookup_subsection(subsection),
            "tax_deductible": is_deductible,
            "explanation": explanation,
            "ruling_date": org.get("ruling_date"),
        }
        return json.dumps(result, indent=2)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return json.dumps({"error": f"No organization found for EIN '{formatted_ein}'.", "tax_deductible": None})
        return json.dumps({"error": f"HTTP error {e.code}: {e.reason}", "tax_deductible": None})
    except Exception as e:
        return json.dumps({"error": f"Verification failed for EIN '{ein}': {e}", "tax_deductible": None})


@mcp.tool()
def classify_charity(ein: str) -> str:
    """Get the full IRS classification and NTEE category for a nonprofit.

    Returns the organization's NTEE code (National Taxonomy of Exempt Entities),
    major group classification, IRS subsection, ruling date, and a summary
    of what type of nonprofit it is.

    Args:
        ein: The 9-digit EIN (e.g. "13-1837418" or "131837418").

    Returns:
        JSON with complete classification details.
    """
    clean = _clean_ein(ein)
    if not clean.isdigit() or len(clean) != 9:
        return json.dumps({"error": f"Invalid EIN '{ein}'. Must be 9 digits."})

    formatted_ein = f"{clean[:2]}-{clean[2:]}"
    try:
        url = f"{BASE_URL}/organizations/{clean}.json"
        data = _fetch_json(url)

        org = data.get("organization", {})
        ntee = _classify_ntee(org.get("ntee_code"))
        subsection = str(org.get("subseccd", org.get("subsection_code", "")))

        result = {
            "ein": formatted_ein,
            "name": org.get("name"),
            "city": org.get("city"),
            "state": org.get("state"),
            "ntee_code": ntee["ntee_code"],
            "ntee_major_group": ntee["major_group"],
            "ntee_major_group_name": ntee["major_group_name"],
            "subsection_code": subsection,
            "subsection_description": _lookup_subsection(subsection),
            "tax_deductible": subsection in ("03", "3"),
            "ruling_date": org.get("ruling_date"),
            "classification_summary": (
                f"{org.get('name', 'Unknown')} is a {ntee['major_group_name'] or 'Unknown'} "
                f"organization classified under "
                f"{_lookup_subsection(subsection)}."
            ),
        }
        return json.dumps(result, indent=2)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return json.dumps({"error": f"No organization found for EIN '{formatted_ein}'."})
        return json.dumps({"error": f"HTTP error {e.code}: {e.reason}"})
    except Exception as e:
        return json.dumps({"error": f"Classification failed for EIN '{ein}': {e}"})


@mcp.tool()
def get_charity_financials(ein: str, years: int = 3) -> str:
    """Get financial summary from recent Form 990 filings for a nonprofit.

    Returns revenue, expenses, net income, assets, and liabilities for the
    most recent filings. Useful for donor due diligence and financial health
    assessment.

    Args:
        ein: The 9-digit EIN (e.g. "13-1837418" or "131837418").
        years: Number of recent filing years to include (default 3, max 10).

    Returns:
        JSON with financial filing data and trend indicators.
    """
    clean = _clean_ein(ein)
    if not clean.isdigit() or len(clean) != 9:
        return json.dumps({"error": f"Invalid EIN '{ein}'. Must be 9 digits."})

    years = min(max(years, 1), 10)
    formatted_ein = f"{clean[:2]}-{clean[2:]}"

    try:
        url = f"{BASE_URL}/organizations/{clean}.json"
        data = _fetch_json(url)

        org = data.get("organization", {})
        filings_list = data.get("filings_with_data", [])

        recent = [_format_filing(f) for f in filings_list[:years]]

        # Compute revenue trend if we have 2+ filings
        trend = None
        if len(recent) >= 2:
            rev_latest = recent[0].get("total_revenue")
            rev_prev = recent[1].get("total_revenue")
            if rev_latest is not None and rev_prev is not None and rev_prev != 0:
                change_pct = round(((rev_latest - rev_prev) / abs(rev_prev)) * 100, 1)
                trend = {
                    "revenue_change_pct": change_pct,
                    "direction": "growing" if change_pct > 5 else "declining" if change_pct < -5 else "stable",
                    "comparison_years": f"{recent[1].get('tax_period')} to {recent[0].get('tax_period')}",
                }

        result = {
            "ein": formatted_ein,
            "name": org.get("name"),
            "city": org.get("city"),
            "state": org.get("state"),
            "filings_available": len(filings_list),
            "filings_returned": len(recent),
            "filings": recent,
            "revenue_trend": trend,
        }
        return json.dumps(result, indent=2)

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return json.dumps({"error": f"No organization found for EIN '{formatted_ein}'."})
        return json.dumps({"error": f"HTTP error {e.code}: {e.reason}"})
    except Exception as e:
        return json.dumps({"error": f"Failed to get financials for EIN '{ein}': {e}"})


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
