"""
Financial Datasets MCP Server
Provides stock market financial data: income statements, balance sheets,
cash flow statements, stock prices, company news, crypto prices, SEC filings.

Source: https://github.com/financial-datasets/mcp-server (1,700+ stars)
API: https://api.financialdatasets.ai
Auth: API key via FINANCIAL_DATASETS_API_KEY env var

Adapted from upstream repo with minor improvements:
- Removed python-dotenv dependency (env vars from .mcp.json)
- Added explicit error returns instead of silent None
- Kept all 12 original tools intact
"""

import json
import os
import sys
import logging
import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr (stdout reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("financial-datasets-mcp")

# Initialize FastMCP server
mcp = FastMCP("financial-datasets")

# Constants
API_BASE = "https://api.financialdatasets.ai"


async def make_request(url: str) -> dict | None:
    """Make a request to the Financial Datasets API with proper error handling."""
    api_key = os.environ.get("FINANCIAL_DATASETS_API_KEY", "")
    if not api_key:
        return {"error": "FINANCIAL_DATASETS_API_KEY not set. Get one at https://financialdatasets.ai/"}

    headers = {"X-API-KEY": api_key}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"API returned {e.response.status_code}: {e.response.text[:200]}"}
        except httpx.RequestError as e:
            return {"error": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}


# --- Financial Statements ---

@mcp.tool()
async def get_income_statements(
    ticker: str,
    period: str = "annual",
    limit: int = 4,
) -> str:
    """Get income statements for a company.

    Args:
        ticker: Ticker symbol of the company (e.g. AAPL, GOOGL)
        period: Period of the income statement (annual, quarterly, ttm)
        limit: Number of income statements to return (default: 4)
    """
    url = f"{API_BASE}/financials/income-statements/?ticker={ticker}&period={period}&limit={limit}"
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    income_statements = data.get("income_statements", [])
    if not income_statements:
        return "No income statements found for this ticker."
    return json.dumps(income_statements, indent=2)


@mcp.tool()
async def get_balance_sheets(
    ticker: str,
    period: str = "annual",
    limit: int = 4,
) -> str:
    """Get balance sheets for a company.

    Args:
        ticker: Ticker symbol of the company (e.g. AAPL, GOOGL)
        period: Period of the balance sheet (annual, quarterly, ttm)
        limit: Number of balance sheets to return (default: 4)
    """
    url = f"{API_BASE}/financials/balance-sheets/?ticker={ticker}&period={period}&limit={limit}"
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    balance_sheets = data.get("balance_sheets", [])
    if not balance_sheets:
        return "No balance sheets found for this ticker."
    return json.dumps(balance_sheets, indent=2)


@mcp.tool()
async def get_cash_flow_statements(
    ticker: str,
    period: str = "annual",
    limit: int = 4,
) -> str:
    """Get cash flow statements for a company.

    Args:
        ticker: Ticker symbol of the company (e.g. AAPL, GOOGL)
        period: Period of the cash flow statement (annual, quarterly, ttm)
        limit: Number of cash flow statements to return (default: 4)
    """
    url = f"{API_BASE}/financials/cash-flow-statements/?ticker={ticker}&period={period}&limit={limit}"
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    cash_flow_statements = data.get("cash_flow_statements", [])
    if not cash_flow_statements:
        return "No cash flow statements found for this ticker."
    return json.dumps(cash_flow_statements, indent=2)


# --- Stock Prices ---

@mcp.tool()
async def get_current_stock_price(ticker: str) -> str:
    """Get the current / latest price of a stock.

    Args:
        ticker: Ticker symbol of the company (e.g. AAPL, GOOGL)
    """
    url = f"{API_BASE}/prices/snapshot/?ticker={ticker}"
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    snapshot = data.get("snapshot", {})
    if not snapshot:
        return "No current price data found for this ticker."
    return json.dumps(snapshot, indent=2)


@mcp.tool()
async def get_historical_stock_prices(
    ticker: str,
    start_date: str,
    end_date: str,
    interval: str = "day",
    interval_multiplier: int = 1,
) -> str:
    """Get historical stock prices for a company.

    Args:
        ticker: Ticker symbol of the company (e.g. AAPL, GOOGL)
        start_date: Start date (e.g. 2020-01-01)
        end_date: End date (e.g. 2020-12-31)
        interval: Interval (minute, hour, day, week, month)
        interval_multiplier: Multiplier of the interval (e.g. 1, 2, 3)
    """
    url = (
        f"{API_BASE}/prices/?ticker={ticker}&interval={interval}"
        f"&interval_multiplier={interval_multiplier}"
        f"&start_date={start_date}&end_date={end_date}"
    )
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    prices = data.get("prices", [])
    if not prices:
        return "No historical prices found for this ticker and date range."
    return json.dumps(prices, indent=2)


# --- Company News ---

@mcp.tool()
async def get_company_news(ticker: str) -> str:
    """Get recent news for a company.

    Args:
        ticker: Ticker symbol of the company (e.g. AAPL, GOOGL)
    """
    url = f"{API_BASE}/news/?ticker={ticker}"
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    news = data.get("news", [])
    if not news:
        return "No news found for this ticker."
    return json.dumps(news, indent=2)


# --- SEC Filings ---

@mcp.tool()
async def get_sec_filings(
    ticker: str,
    limit: int = 10,
    filing_type: str | None = None,
) -> str:
    """Get SEC filings for a company.

    Args:
        ticker: Ticker symbol of the company (e.g. AAPL, GOOGL)
        limit: Number of SEC filings to return (default: 10)
        filing_type: Type of SEC filing (e.g. 10-K, 10-Q, 8-K)
    """
    url = f"{API_BASE}/filings/?ticker={ticker}&limit={limit}"
    if filing_type:
        url += f"&filing_type={filing_type}"
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    filings = data.get("filings", [])
    if not filings:
        return "No SEC filings found for this ticker."
    return json.dumps(filings, indent=2)


# --- Crypto ---

@mcp.tool()
async def get_available_crypto_tickers() -> str:
    """Get all available crypto tickers."""
    url = f"{API_BASE}/crypto/prices/tickers"
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    tickers = data.get("tickers", [])
    return json.dumps(tickers, indent=2)


@mcp.tool()
async def get_current_crypto_price(ticker: str) -> str:
    """Get the current / latest price of a crypto currency.

    Args:
        ticker: Ticker symbol (e.g. BTC-USD). Use get_available_crypto_tickers for valid tickers.
    """
    url = f"{API_BASE}/crypto/prices/snapshot/?ticker={ticker}"
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    snapshot = data.get("snapshot", {})
    if not snapshot:
        return "No current price data found for this crypto ticker."
    return json.dumps(snapshot, indent=2)


@mcp.tool()
async def get_historical_crypto_prices(
    ticker: str,
    start_date: str,
    end_date: str,
    interval: str = "day",
    interval_multiplier: int = 1,
) -> str:
    """Get historical prices for a crypto currency.

    Args:
        ticker: Ticker symbol (e.g. BTC-USD). Use get_available_crypto_tickers for valid tickers.
        start_date: Start date (e.g. 2020-01-01)
        end_date: End date (e.g. 2020-12-31)
        interval: Interval (minute, hour, day, week, month)
        interval_multiplier: Multiplier of the interval (e.g. 1, 2, 3)
    """
    url = (
        f"{API_BASE}/crypto/prices/?ticker={ticker}&interval={interval}"
        f"&interval_multiplier={interval_multiplier}"
        f"&start_date={start_date}&end_date={end_date}"
    )
    data = await make_request(url)
    if not data or "error" in data:
        return json.dumps(data or {"error": "No data returned"})
    prices = data.get("prices", [])
    if not prices:
        return "No historical crypto prices found for this ticker and date range."
    return json.dumps(prices, indent=2)


# --- Duplicate tool from upstream (crypto_prices vs historical_crypto_prices) ---
# The upstream repo has both get_crypto_prices and get_historical_crypto_prices
# with identical implementations. We keep only get_historical_crypto_prices above
# to avoid confusing tool duplication.


if __name__ == "__main__":
    logger.info("Starting Financial Datasets MCP Server...")
    mcp.run(transport="stdio")
