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

### `quote_spend`
Pre-flights a spend request without writing a transaction. Validates category
(`tool_acquisition`, `tool_usage`, `api_call`, `other`) and checks the daily and
monthly caps including active reservations.

**Parameters:**
- `project_slug` (str, required) -- Project receiving the spend
- `vendor` (str, required) -- Vendor receiving payment
- `amount_usd` (float, required) -- Requested amount
- `recurrence` (str, required) -- none, one_time, monthly, or annual
- `category` (str, required) -- Spend category
- `requested_by_tool_stack` (str, optional) -- Tool stack requesting the spend

Returns `OK` with a process-local `quote_id`, or `REJECTED` with cap details.

### `reserve_spend`
Creates a hold from a prior quote and an OAI authorization. The reservation is
stored in the reservation ledger with `state: reserved` and mirrored into the
Markdown spending log as an audit row. Reservations expire automatically on
subsequent spending MCP calls.

**Parameters:**
- `quote_id` (str, required)
- `authorization_id` (str, required) -- From the resolved OAI response
- `expires_at` (str, required) -- ISO timestamp
- `project_slug` (str, optional) -- Match check
- `category` (str, optional) -- Match check
- `max_authorized_amount_usd` (float, optional) -- Operator authorization ceiling

### `capture_spend`
Converts a reservation into actual spend. Capture is idempotent by
`reservation_id`; retrying after success returns the same capture record.
`actual_amount_usd` must be less than or equal to the reserved amount.

**Parameters:**
- `reservation_id` (str, required)
- `actual_amount_usd` (float, required)
- `receipt_ref` (str, required) -- Vault path to the receipt artifact
- `project_slug` (str, optional) -- Match check
- `category` (str, optional) -- Match check

### `release_reservation`
Releases an unused reservation with `actual_amount_usd: 0`. Used for operator
decline, install failure, checksum mismatch, canary failure, or abort. Release
is idempotent for already released/expired reservations.

**Parameters:**
- `reservation_id` (str, required)
- `reason` (str, required)
- `project_slug` (str, optional) -- Match check
- `category` (str, optional) -- Match check

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
| `SPENDING_RESERVATION_LOG_PATH` | No | same directory, `.reservations.json` suffix | JSON reservation/capture/release state ledger |
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

Reservation state is stored in a JSON ledger beside the Markdown log. The
Markdown log remains the human-readable audit trail; the JSON ledger is the
state-machine source of truth for `reserved -> captured | released | expired`.
Captured rows count toward daily/monthly totals; reserved rows count only toward
quote projections.

## Security Notes

- All expenditures are logged regardless of approval status (blocked and rejected transactions are also recorded).
- The spending log is human-readable Markdown for easy auditing.
- Caps are enforced server-side; the agent cannot bypass them.
- Elicitation confirmation adds an inline human gate for the $5-$50 tier, replacing post-hoc review with pre-approval.
- Integrity checksums detect log tampering and block all spending until investigated.
- Capture requires a reservation, and reservations must carry the OAI
  `authorization_id` that authorized the spend.
- Secrets do not belong in spending descriptions, receipt refs, or authorization
  metadata; use vault pointers, env var names, or keychain entry names only.
