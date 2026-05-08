# SEC EDGAR MCP Server

Access SEC EDGAR filing data — company lookup, financial statements (10-K, 10-Q), insider transactions (Form 4), 13F institutional holdings, XBRL facts, and filing content extraction. Uses edgartools library. SEC EDGAR is free government data — no API key needed.

## Setup

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| SEC_EDGAR_IDENTITY | Yes | Your name and email for SEC User-Agent header. Format: `Your Name your.email@example.com` (SEC policy requires contact info) |

### Install Dependencies

```bash
pip install -r requirements.txt
```

## Tools

| Tool | Description |
|------|-------------|
| lookup_company | Look up company info by ticker or CIK — name, SIC, state, exchanges |
| search_filings | Search a company's SEC filings by form type (10-K, 10-Q, 8-K, etc.) |
| get_financial_statements | Get income statement, balance sheet, or cash flow from XBRL data |
| get_insider_transactions | Get Form 4 insider trading data — buys, sells, exercises |
| get_institutional_holdings | Get 13F institutional holdings for a fund or company |
| get_company_facts | Get XBRL facts — structured financial data points with history |
| get_filing_content | Get text content of a specific filing, optionally a specific section |
| search_all_filings | Search recent filings across all companies by form type |

## Registration

Add to `.mcp.json`:
```json
{
  "sec-edgar": {
    "type": "stdio",
    "command": "/path/to/venv/bin/python3",
    "args": ["vault/clients/_platform/mcps/sec-edgar/server.py"],
    "env": {
      "SEC_EDGAR_IDENTITY": "Your Name your.email@example.com"
    }
  }
}
```
