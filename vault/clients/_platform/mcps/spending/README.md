# Spending MCP Server

Agent budget management for the AI agent platform. Enforces tiered spending approval rules and logs all expenditures to a local Markdown file.

Supports **MCP Elicitation** for inline admin confirmation of flagged expenditures ($5-$50 tier). Falls back gracefully when the client does not support elicitation.

## Approval Tiers

| Amount | Behavior |
|--------|----------|
| Under $5 | Auto-approved, logged |
| $5 - $50 | Elicitation confirmation if available; otherwise auto-approved and flagged |
| Over $50 | **BLOCKED** -- agent must create a human-approval ticket |
| Daily total over cap | **BLOCKED** |
| Monthly total over cap | **BLOCKED** |

## Tools

### `check_spending_budget`
Returns current budget status: daily/monthly spent and remaining amounts, caps, and approval tier definitions.

### `record_expenditure`
Records a spending transaction with tiered approval enforcement.

**Parameters:**
- `amount_usd` (float, required) -- Amount in USD
- `description` (str, required) -- What the spend is for
- `vendor` (str, required) -- Who the payment goes to
- `category` (str, default: "api") -- Category: api, hosting, tools, other

### `get_spending_log`
Returns recent spending transactions with summary statistics.

**Parameters:**
- `days` (int, default: 7) -- Number of days of history (1-365)

## MCP Elicitation Integration

This server uses the MCP Elicitation protocol (Form mode) to request inline admin confirmation before recording expenditures in the $5-$50 range.

### How It Works

1. When `record_expenditure` is called with an amount between $5-$50, the server sends an `elicitation/create` request to the client.
2. The client presents a confirmation form to the admin with the expenditure details, an approve/reject toggle, and an optional notes field.
3. If the admin approves, the expenditure is recorded with status `approved-elicitation`.
4. If the admin rejects or cancels, the expenditure is recorded as `REJECTED-elicitation` and the tool returns a rejection response.
5. If elicitation is unavailable (client doesn't support it), the server falls back to the legacy behavior: auto-approve with `flagged-for-review` status.

### Architecture Pattern for Future MCPs

To add MCP Elicitation to any FastMCP server, follow this pattern:

```python
from pydantic import BaseModel, Field
from mcp.server.fastmcp import Context, FastMCP

# 1. Define a flat Pydantic model (only primitive fields: str, bool, int, float, enum)
class MyApproval(BaseModel):
    approved: bool = Field(default=False, title="Approve?", description="...")
    notes: str = Field(default="", title="Notes", description="...")

# 2. Write a helper that wraps elicitation with fallback
async def _request_approval(ctx: Context, message: str) -> tuple[bool, str]:
    try:
        result = await ctx.elicit(message=message, schema=MyApproval)
        if result.action == "accept":
            return result.data.approved, result.data.notes
        elif result.action == "decline":
            return False, "declined"
        else:  # cancel
            return False, "cancelled"
    except Exception:
        # Client doesn't support elicitation -- fall back
        return True, "elicitation-unavailable"

# 3. Accept ctx: Context in your tool handler (FastMCP auto-injects it)
@mcp.tool()
async def my_sensitive_tool(param: str, ctx: Context | None = None) -> str:
    if ctx is not None:
        approved, notes = await _request_approval(ctx, f"Confirm: {param}")
        if notes != "elicitation-unavailable" and not approved:
            return "Rejected by admin."
    # ... proceed with operation ...
```

Key rules:
- Schema must be a flat Pydantic model (no nested objects, no arrays of objects)
- Allowed field types: `str`, `int`, `float`, `bool`, enum via `Literal` or `Field(json_schema_extra={"enum": [...]})`
- Always wrap `ctx.elicit()` in try/except for backward compatibility
- Make tool handlers `async` (required for `await ctx.elicit()`)
- `ctx: Context | None = None` makes Context optional for non-elicitation callers

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SPENDING_LOG_PATH` | No | `vault/config/spending-log.md` | Path to the spending log file |
| `DAILY_CAP_USD` | No | `25` | Maximum daily spending in USD |
| `MONTHLY_CAP_USD` | No | `200` | Maximum monthly spending in USD |

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. (Optional) Configure caps:
   ```bash
   export DAILY_CAP_USD=25
   export MONTHLY_CAP_USD=200
   ```

3. Run the server:
   ```bash
   python3 server.py
   ```

## Spending Log Format

The spending log is a Markdown table at the configured path:

```markdown
# Agent Spending Log

| Timestamp | Amount (USD) | Vendor | Category | Description | Status |
|-----------|-------------|--------|----------|-------------|--------|
| 2026-03-17 12:00:00 UTC | $2.50 | OpenAI | api | GPT-4 API call | approved |
| 2026-03-17 13:00:00 UTC | $15.00 | AWS | hosting | EC2 instance | approved-elicitation |
| 2026-03-17 13:30:00 UTC | $8.00 | Vendor | api | Rejected spend | REJECTED-elicitation: too expensive |
| 2026-03-17 14:00:00 UTC | $75.00 | Anthropic | api | Claude batch job | BLOCKED |
```

## Security Notes

- All expenditures are logged regardless of approval status (blocked and rejected transactions are also recorded).
- The spending log is human-readable Markdown for easy auditing.
- Caps are enforced server-side; the agent cannot bypass them.
- Elicitation confirmation adds an inline human gate for the $5-$50 tier, replacing post-hoc review with pre-approval.
- Integrity checksums detect log tampering and block all spending until investigated.
