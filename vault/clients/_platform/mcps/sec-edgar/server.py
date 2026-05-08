"""
SEC EDGAR MCP Server
Access SEC EDGAR filing data — company lookup, financial statements,
insider transactions, 13F institutional holdings, and filing search.
Uses edgartools library. SEC EDGAR is free government data (no API key).
"""

import os
import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("sec-edgar")


# --- Configuration ---

SEC_EDGAR_IDENTITY = os.environ.get("SEC_EDGAR_IDENTITY", "")


# --- Helpers ---

def _init_edgar():
    """Initialize edgartools with SEC-required identity."""
    from edgar import set_identity
    if SEC_EDGAR_IDENTITY:
        set_identity(SEC_EDGAR_IDENTITY)
    else:
        raise ValueError(
            "SEC_EDGAR_IDENTITY env var is required. "
            "Format: 'Your Name your.email@example.com' "
            "(SEC policy requires a User-Agent with contact info)"
        )


def _filing_to_dict(filing) -> dict:
    """Convert an edgartools Filing object to a serializable dict."""
    return {
        "accession_number": str(getattr(filing, "accession_no", "")),
        "form_type": str(getattr(filing, "form", "")),
        "filing_date": str(getattr(filing, "filing_date", "")),
        "company": str(getattr(filing, "company", "")),
        "cik": str(getattr(filing, "cik", "")),
        "url": str(getattr(filing, "filing_url", getattr(filing, "url", ""))),
    }


def _dataframe_to_records(df, max_rows: int = 50) -> list:
    """Convert a pandas DataFrame to a list of dicts, capped at max_rows."""
    if df is None:
        return []
    try:
        # Reset index so index columns become regular columns
        df_reset = df.reset_index()
        records = df_reset.head(max_rows).to_dict(orient="records")
        # Convert any non-serializable values to strings
        clean = []
        for row in records:
            clean.append({k: str(v) if not isinstance(v, (int, float, bool, type(None))) else v
                          for k, v in row.items()})
        return clean
    except Exception:
        return [{"raw": str(df)[:2000]}]


# --- Tools ---

@mcp.tool()
def lookup_company(ticker_or_cik: str) -> str:
    """Look up a company by ticker symbol or CIK number. Returns company
    name, CIK, ticker(s), SIC code, state, fiscal year end, and filing counts.

    Args:
        ticker_or_cik: Ticker symbol (e.g. 'AAPL') or CIK number (e.g. '0000320193')

    Returns:
        JSON with company information
    """
    try:
        _init_edgar()
        from edgar import Company
        company = Company(ticker_or_cik)
        info = {
            "name": str(getattr(company, "name", "")),
            "cik": str(getattr(company, "cik", "")),
            "tickers": [str(t) for t in getattr(company, "tickers", [])],
            "sic_code": str(getattr(company, "sic", "")),
            "sic_description": str(getattr(company, "sic_description", "")),
            "state": str(getattr(company, "state_of_incorporation", "")),
            "fiscal_year_end": str(getattr(company, "fiscal_year_end", "")),
            "exchanges": [str(e) for e in getattr(company, "exchanges", [])],
        }
        return json.dumps(info, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def search_filings(
    ticker_or_cik: str,
    form_type: str = "10-K",
    max_results: int = 5
) -> str:
    """Search SEC filings for a company by form type.

    Args:
        ticker_or_cik: Ticker symbol or CIK number
        form_type: Filing form type — '10-K', '10-Q', '8-K', '4', '13F-HR', 'DEF 14A', etc.
        max_results: Maximum number of filings to return (default: 5, max: 20)

    Returns:
        JSON array of filing summaries with accession numbers, dates, and URLs
    """
    try:
        _init_edgar()
        from edgar import Company
        max_results = min(max_results, 20)
        company = Company(ticker_or_cik)
        filings = company.get_filings(form=form_type)
        results = []
        for i, filing in enumerate(filings):
            if i >= max_results:
                break
            results.append(_filing_to_dict(filing))
        return json.dumps({"company": str(company.name), "form_type": form_type,
                           "count": len(results), "filings": results}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_financial_statements(
    ticker_or_cik: str,
    statement: str = "income_statement",
    period: str = "annual"
) -> str:
    """Get financial statements (income statement, balance sheet, or cash flow)
    from a company's most recent XBRL filings.

    Args:
        ticker_or_cik: Ticker symbol or CIK number
        statement: Which statement — 'income_statement', 'balance_sheet', or 'cash_flow'
        period: 'annual' or 'quarterly'

    Returns:
        JSON with financial statement data (line items and values)
    """
    try:
        _init_edgar()
        from edgar import Company
        company = Company(ticker_or_cik)

        # get_financials() for annual, get_quarterly_financials() for quarterly
        if period == "quarterly":
            financials = company.get_quarterly_financials()
        else:
            financials = company.get_financials()

        # income_statement(), balance_sheet(), cash_flow_statement() are methods
        if statement == "income_statement":
            data = financials.income_statement()
        elif statement == "balance_sheet":
            data = financials.balance_sheet()
        elif statement == "cash_flow":
            data = financials.cash_flow_statement()
        else:
            return json.dumps({"error": f"Unknown statement type: {statement}. "
                               "Use 'income_statement', 'balance_sheet', or 'cash_flow'."})

        # Convert to a serializable format
        result = {
            "company": str(company.name),
            "statement": statement,
            "period": period,
            "data": str(data)[:5000],
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_insider_transactions(
    ticker_or_cik: str,
    max_filings: int = 10
) -> str:
    """Get insider trading transactions (Form 4 filings) for a company.
    Shows insider buys, sells, option exercises, and grants.

    Args:
        ticker_or_cik: Ticker symbol or CIK number
        max_filings: Maximum number of Form 4 filings to process (default: 10, max: 25)

    Returns:
        JSON with insider transaction details
    """
    try:
        _init_edgar()
        from edgar import Company
        max_filings = min(max_filings, 25)
        company = Company(ticker_or_cik)
        filings = company.get_filings(form="4")
        transactions = []

        for i, filing in enumerate(filings):
            if i >= max_filings:
                break
            try:
                form4 = filing.obj()
                tx_info = {
                    "filing_date": str(getattr(filing, "filing_date", "")),
                    "accession_number": str(getattr(filing, "accession_no", "")),
                    "url": str(getattr(filing, "filing_url", getattr(filing, "url", ""))),
                }

                # Get insider identity
                tx_info["insider_name"] = str(getattr(form4, "insider_name", ""))
                tx_info["position"] = str(getattr(form4, "position", ""))

                # Get transaction data via to_dataframe()
                try:
                    df = form4.to_dataframe()
                    tx_info["transactions"] = _dataframe_to_records(df, max_rows=20)
                except Exception:
                    # Fallback to ownership summary
                    try:
                        summary = form4.get_ownership_summary()
                        tx_info["transactions"] = str(summary)[:1500]
                    except Exception:
                        tx_info["transactions"] = str(form4)[:1000]

                transactions.append(tx_info)
            except Exception as inner_e:
                transactions.append({
                    "filing_date": str(getattr(filing, "filing_date", "")),
                    "parse_error": str(inner_e)
                })

        return json.dumps({
            "company": str(company.name),
            "form_type": "4",
            "filings_processed": len(transactions),
            "insider_transactions": transactions
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_institutional_holdings(
    ticker_or_cik: str,
    max_results: int = 5
) -> str:
    """Get 13F institutional holdings filings for a company or fund.
    Shows what institutions hold which stocks and positions sizes.

    For a company ticker: finds 13F filers that hold that stock.
    For a fund CIK: returns the fund's 13F portfolio holdings.

    Args:
        ticker_or_cik: Ticker symbol of a company or CIK of a 13F filer (fund/institution)
        max_results: Maximum number of 13F filings to return (default: 5, max: 10)

    Returns:
        JSON with institutional holdings data
    """
    try:
        _init_edgar()
        from edgar import Company, get_filings
        max_results = min(max_results, 10)

        # Try as a 13F filer first (institutions file 13F-HR)
        try:
            company = Company(ticker_or_cik)
            filings = company.get_filings(form="13F-HR")
            results = []

            for i, filing in enumerate(filings):
                if i >= max_results:
                    break
                try:
                    thirteenf = filing.obj()
                    holdings = getattr(thirteenf, "holdings", None)
                    filing_info = {
                        "filing_date": str(getattr(filing, "filing_date", "")),
                        "accession_number": str(getattr(filing, "accession_no", "")),
                        "url": str(getattr(filing, "filing_url", getattr(filing, "url", ""))),
                    }
                    if holdings is not None:
                        filing_info["holdings_count"] = len(holdings) if hasattr(holdings, "__len__") else 0
                        filing_info["holdings"] = _dataframe_to_records(holdings, max_rows=30)
                    else:
                        filing_info["holdings"] = str(thirteenf)[:2000]
                    results.append(filing_info)
                except Exception as inner_e:
                    results.append({
                        "filing_date": str(getattr(filing, "filing_date", "")),
                        "parse_error": str(inner_e)
                    })

            return json.dumps({
                "entity": str(company.name),
                "form_type": "13F-HR",
                "filings_found": len(results),
                "filings": results
            }, indent=2)
        except Exception:
            # If the entity doesn't have 13F filings, try searching globally
            filings = get_filings(form="13F-HR")
            recent = []
            for i, f in enumerate(filings):
                if i >= max_results:
                    break
                recent.append(_filing_to_dict(f))
            return json.dumps({
                "note": f"No 13F filings found for '{ticker_or_cik}'. Showing recent 13F filings globally.",
                "recent_13f_filings": recent
            }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_company_facts(
    ticker_or_cik: str,
    fact_name: str = ""
) -> str:
    """Get XBRL facts for a company from SEC EDGAR. Facts are structured
    financial data points (revenue, assets, shares outstanding, etc.).

    Without a fact_name, returns available fact categories.
    With a fact_name, returns historical values for that specific fact.

    Args:
        ticker_or_cik: Ticker symbol or CIK number
        fact_name: Specific XBRL fact name (e.g. 'Revenues', 'Assets'). Leave empty to list available facts.

    Returns:
        JSON with XBRL fact data
    """
    try:
        _init_edgar()
        from edgar import Company
        company = Company(ticker_or_cik)
        facts = company.get_facts()

        if not fact_name:
            # List available fact categories
            try:
                # Get the facts object and list its contents
                fact_str = str(facts)
                return json.dumps({
                    "company": str(company.name),
                    "facts_summary": fact_str[:3000],
                    "hint": "Provide a specific fact_name (e.g. 'Revenues', 'Assets', "
                            "'NetIncomeLoss') to get historical values."
                }, indent=2)
            except Exception:
                return json.dumps({
                    "company": str(company.name),
                    "facts": str(facts)[:3000]
                }, indent=2)
        else:
            # Get specific fact values
            try:
                fact_data = facts[fact_name]
                return json.dumps({
                    "company": str(company.name),
                    "fact": fact_name,
                    "data": str(fact_data)[:4000]
                }, indent=2)
            except (KeyError, IndexError):
                return json.dumps({
                    "company": str(company.name),
                    "error": f"Fact '{fact_name}' not found. Use this tool without "
                             "a fact_name to see available facts."
                }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_filing_content(
    ticker_or_cik: str,
    form_type: str = "10-K",
    filing_index: int = 0,
    section: str = ""
) -> str:
    """Get the text content of a specific SEC filing. Can extract specific
    sections from 10-K and 10-Q filings.

    Args:
        ticker_or_cik: Ticker symbol or CIK number
        form_type: Filing form type (e.g. '10-K', '10-Q', '8-K')
        filing_index: Which filing to get (0 = most recent, 1 = second most recent, etc.)
        section: For 10-K/10-Q, a named section like 'business', 'risk_factors',
                 'management_discussion'. Leave empty to get a summary with available sections.

    Returns:
        JSON with filing content text (truncated to manageable size)
    """
    try:
        _init_edgar()
        from edgar import Company
        company = Company(ticker_or_cik)
        filings = company.get_filings(form=form_type)

        if filing_index >= len(filings):
            return json.dumps({"error": f"Filing index {filing_index} out of range. "
                               f"Only {len(filings)} {form_type} filings available."})

        filing = filings[filing_index]
        filing_obj = filing.obj()

        result = {
            "company": str(company.name),
            "form_type": form_type,
            "filing_date": str(getattr(filing, "filing_date", "")),
            "url": str(getattr(filing, "filing_url", getattr(filing, "url", ""))),
        }

        if section:
            # Try to extract a specific named section (e.g. business, risk_factors)
            try:
                section_content = getattr(filing_obj, section, None)
                if section_content is not None:
                    result["section"] = section
                    result["content"] = str(section_content)[:5000]
                elif hasattr(filing_obj, "__getitem__"):
                    result["section"] = section
                    result["content"] = str(filing_obj[section])[:5000]
                else:
                    result["section_error"] = f"Section '{section}' not found."
                    # List available sections
                    items = getattr(filing_obj, "items", [])
                    result["available_items"] = items[:20] if items else []
            except Exception as sec_e:
                result["section_error"] = f"Could not extract section '{section}': {str(sec_e)}"
        else:
            # Return a summary: available items/sections and filing metadata
            items = getattr(filing_obj, "items", [])
            sections_obj = getattr(filing_obj, "sections", None)
            result["available_items"] = items[:25] if items else []
            result["sections_summary"] = str(sections_obj)[:2000] if sections_obj else ""

            # For 10-K/10-Q, include key named sections if available
            for attr in ["business", "risk_factors", "management_discussion"]:
                val = getattr(filing_obj, attr, None)
                if val is not None:
                    result[f"{attr}_preview"] = str(val)[:500]

        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def search_all_filings(
    form_type: str = "10-K",
    max_results: int = 10
) -> str:
    """Search recent SEC filings across all companies by form type.
    Useful for finding recent 13F filings, 8-K events, or insider activity.

    Args:
        form_type: Filing form type — '10-K', '10-Q', '8-K', '4', '13F-HR', etc.
        max_results: Maximum number of filings to return (default: 10, max: 25)

    Returns:
        JSON array of recent filings of the specified type
    """
    try:
        _init_edgar()
        from edgar import get_filings
        max_results = min(max_results, 25)
        filings = get_filings(form=form_type)
        results = []
        for i, filing in enumerate(filings):
            if i >= max_results:
                break
            results.append(_filing_to_dict(filing))
        return json.dumps({
            "form_type": form_type,
            "count": len(results),
            "filings": results
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- Entry Point ---

if __name__ == "__main__":
    mcp.run()
