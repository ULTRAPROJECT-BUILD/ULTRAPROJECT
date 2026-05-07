"""
Spending MCP Server — Agent Budget Management

Manages the AI agent's spending budget on a pre-funded card.
Enforces tiered approval rules, daily/monthly caps, and logs all expenditures
to a local Markdown file.

Supports MCP Elicitation (protocol-native structured input requests) for
inline admin confirmation of expenditures in the $5-$50 range. Falls back
gracefully when the client does not advertise elicitation capability.

Elicitation architecture pattern:
  1. Import Context from mcp.server.fastmcp and accept `ctx: Context` in tools
  2. Define a Pydantic model with only primitive fields for the elicitation schema
  3. Call `await ctx.elicit(message, SchemaModel)` inside async tool handlers
  4. Check result.action: "accept" -> proceed, "decline"/"cancel" -> abort
  5. Wrap elicitation in try/except to degrade gracefully on unsupported clients
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from mcp.server.fastmcp import Context, FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SPENDING_LOG_PATH = os.environ.get(
    "SPENDING_LOG_PATH", "vault/config/spending-log.md"
)
DAILY_CAP_USD = float(os.environ.get("DAILY_CAP_USD", "25"))
MONTHLY_CAP_USD = float(os.environ.get("MONTHLY_CAP_USD", "200"))

# Resolve relative paths against the working directory
_log_path = Path(SPENDING_LOG_PATH)
if not _log_path.is_absolute():
    _log_path = Path.cwd() / _log_path
SPENDING_LOG_FILE = _log_path

# ---------------------------------------------------------------------------
# Spending log helpers
# ---------------------------------------------------------------------------


def _ensure_log_exists() -> None:
    """Create the spending log file if it doesn't exist."""
    SPENDING_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SPENDING_LOG_FILE.exists():
        header = (
            "# Agent Spending Log\n\n"
            "| Timestamp | Amount (USD) | Vendor | Category | Description | Status |\n"
            "|-----------|-------------|--------|----------|-------------|--------|\n"
        )
        SPENDING_LOG_FILE.write_text(header, encoding="utf-8")


def _parse_log_entries() -> list[dict]:
    """Parse all entries from the spending log."""
    _ensure_log_exists()
    content = SPENDING_LOG_FILE.read_text(encoding="utf-8")
    entries = []

    for line in content.strip().split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip header and separator rows
        parts = [p.strip() for p in line.split("|")]
        # Filter out empty strings from leading/trailing pipes
        parts = [p for p in parts if p]
        if len(parts) < 6:
            continue
        if parts[0] in ("Timestamp", "-----------", "---"):
            continue
        if parts[0].startswith("---"):
            continue

        try:
            timestamp_str = parts[0]
            amount = float(parts[1].replace("$", "").replace(",", ""))
            vendor = parts[2]
            category = parts[3]
            description = parts[4]
            status = parts[5]

            entries.append(
                {
                    "timestamp": timestamp_str,
                    "amount_usd": amount,
                    "vendor": vendor,
                    "category": category,
                    "description": description,
                    "status": status,
                }
            )
        except (ValueError, IndexError):
            continue

    return entries


def _integrity_path() -> Path:
    """Path to the integrity checksum file (protected by restrict-paths hook)."""
    return SPENDING_LOG_FILE.parent / ".spending-integrity"


def _compute_file_hash() -> str:
    """Compute SHA-256 hash of the spending log content."""
    try:
        content = SPENDING_LOG_FILE.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except FileNotFoundError:
        return ""


def _write_integrity() -> None:
    """Write the current spending log hash to the integrity file."""
    file_hash = _compute_file_hash()
    entry_count = 0
    try:
        content = SPENDING_LOG_FILE.read_text(encoding="utf-8")
        for line in content.strip().split("\n"):
            line = line.strip()
            if line.startswith("|") and not line.startswith("| Timestamp") and not line.startswith("|---"):
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 6 and not parts[0].startswith("---"):
                    entry_count += 1
    except FileNotFoundError:
        pass
    integrity_file = _integrity_path()
    integrity_file.write_text(
        f"{file_hash}\n{entry_count}\n",
        encoding="utf-8",
    )


def _verify_integrity() -> tuple[bool, str]:
    """Verify spending log has not been tampered with.

    Returns (is_valid, reason). If the integrity file doesn't exist yet,
    initializes it and returns valid (first-run case).
    """
    integrity_file = _integrity_path()
    if not integrity_file.exists():
        # If the spending log has existing entries but no integrity file,
        # someone may have deleted the integrity file to reset the baseline.
        # Only auto-initialize on truly empty/new logs.
        if SPENDING_LOG_FILE.exists():
            content = SPENDING_LOG_FILE.read_text(encoding="utf-8")
            has_entries = False
            for line in content.strip().split("\n"):
                line = line.strip()
                if line.startswith("|") and not line.startswith("| Timestamp") and not line.startswith("|---"):
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 6 and not parts[0].startswith("---"):
                        has_entries = True
                        break
            if has_entries:
                return False, "integrity file missing but spending log has entries — possible tampering"
        _write_integrity()
        return True, "integrity initialized"

    try:
        parts = integrity_file.read_text(encoding="utf-8").strip().split("\n")
        stored_hash = parts[0] if len(parts) > 0 else ""
        stored_count = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, FileNotFoundError):
        return False, "integrity file corrupted"

    current_hash = _compute_file_hash()
    if not current_hash:
        if stored_hash == "":
            return True, "both empty"
        return False, "spending log deleted but integrity file exists"

    # Count current entries
    current_count = 0
    try:
        content = SPENDING_LOG_FILE.read_text(encoding="utf-8")
        for line in content.strip().split("\n"):
            line = line.strip()
            if line.startswith("|") and not line.startswith("| Timestamp") and not line.startswith("|---"):
                entry_parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(entry_parts) >= 6 and not entry_parts[0].startswith("---"):
                    current_count += 1
    except FileNotFoundError:
        return False, "spending log missing"

    if current_hash != stored_hash:
        return False, f"hash mismatch (entries: stored={stored_count}, current={current_count})"

    return True, "ok"


def _append_log_entry(
    amount_usd: float,
    vendor: str,
    category: str,
    description: str,
    status: str,
) -> None:
    """Append a new entry to the spending log and update integrity checksum."""
    _ensure_log_exists()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"| {timestamp} | ${amount_usd:.2f} | {vendor} | {category} | {description} | {status} |\n"
    with open(SPENDING_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    _write_integrity()


def _compute_totals(entries: list[dict]) -> dict:
    """Compute daily and monthly spending totals from approved entries."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    month_str = now.strftime("%Y-%m")

    daily_total = 0.0
    monthly_total = 0.0

    for entry in entries:
        # Only count approved transactions (including elicitation-approved)
        status = entry.get("status", "").lower()
        if status not in ("approved", "flagged-for-review", "approved-elicitation"):
            continue

        ts = entry.get("timestamp", "")
        if ts.startswith(today_str):
            daily_total += entry["amount_usd"]
        if ts.startswith(month_str):
            monthly_total += entry["amount_usd"]

    return {
        "daily_spent": daily_total,
        "daily_remaining": max(0, DAILY_CAP_USD - daily_total),
        "monthly_spent": monthly_total,
        "monthly_remaining": max(0, MONTHLY_CAP_USD - monthly_total),
    }


# ---------------------------------------------------------------------------
# Elicitation schema — Pydantic model for inline confirmation
# ---------------------------------------------------------------------------


class SpendApproval(BaseModel):
    """Schema for admin confirmation of a flagged expenditure.

    Used by MCP Elicitation Form mode. Only primitive fields are allowed
    (string, number, boolean, enum). No nested objects.
    """

    approved: bool = Field(
        default=False,
        title="Approve this expenditure?",
        description="Set to true to approve, false to reject.",
    )
    notes: str = Field(
        default="",
        title="Notes (optional)",
        description="Optional reason or notes for the decision.",
    )


async def _elicit_spend_approval(
    ctx: Context,
    amount_usd: float,
    vendor: str,
    description: str,
    category: str,
    daily_spent: float,
    daily_remaining: float,
) -> tuple[bool, str]:
    """Request inline admin approval via MCP Elicitation.

    Returns (approved: bool, notes: str).
    If elicitation is unavailable, returns (True, "elicitation-unavailable")
    to preserve backward compatibility (auto-approve with flag).
    """
    message = (
        f"SPENDING CONFIRMATION REQUIRED\n\n"
        f"Amount: ${amount_usd:.2f}\n"
        f"Vendor: {vendor}\n"
        f"Category: {category}\n"
        f"Description: {description}\n\n"
        f"Daily spent so far: ${daily_spent:.2f} / ${DAILY_CAP_USD:.2f}\n"
        f"Daily remaining after: ${daily_remaining - amount_usd:.2f}\n\n"
        f"This expenditure is in the $5-$50 flagged tier. "
        f"Please approve or reject."
    )
    try:
        result = await ctx.elicit(message=message, schema=SpendApproval)

        if result.action == "accept":
            return result.data.approved, (result.data.notes or "")
        elif result.action == "decline":
            return False, "admin-declined"
        else:  # cancel
            return False, "admin-cancelled"

    except Exception as exc:
        # Elicitation not supported by this client, or other error.
        # Fall back to auto-approve with flag (backward compat).
        logger.debug("Elicitation unavailable, falling back: %s", exc)
        return True, "elicitation-unavailable"


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Agent Spending Budget",
    instructions=(
        "Manages the AI agent's spending budget with tiered approval rules "
        f"and caps (daily: ${DAILY_CAP_USD}, monthly: ${MONTHLY_CAP_USD}). "
        "Logs all expenditures to a local Markdown file. "
        "Supports MCP Elicitation for inline admin confirmation of flagged expenditures."
    ),
)


@mcp.tool()
async def check_spending_budget() -> str:
    """Check the current spending budget status.

    Returns:
        Daily spent/remaining, monthly spent/remaining, and cap information.
    """
    try:
        entries = _parse_log_entries()
        totals = _compute_totals(entries)

        result = {
            "daily_cap_usd": DAILY_CAP_USD,
            "daily_spent_usd": round(totals["daily_spent"], 2),
            "daily_remaining_usd": round(totals["daily_remaining"], 2),
            "monthly_cap_usd": MONTHLY_CAP_USD,
            "monthly_spent_usd": round(totals["monthly_spent"], 2),
            "monthly_remaining_usd": round(totals["monthly_remaining"], 2),
            "log_file": str(SPENDING_LOG_FILE),
            "approval_tiers": {
                "auto_approved": "Under $5.00",
                "flagged_for_review": "$5.00 - $50.00 (elicitation confirmation if available)",
                "blocked_requires_human": "Over $50.00",
            },
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return f"Error: Failed to check spending budget — {e}"


@mcp.tool()
async def record_expenditure(
    amount_usd: float,
    description: str,
    vendor: str,
    category: str = "api",
    ctx: Context | None = None,
) -> str:
    """Record a spending transaction. Enforces tiered approval limits.

    Approval tiers:
    - Under $5: auto-approved, logged
    - $5-$50: inline elicitation confirmation (if available), then logged
    - Over $50: BLOCKED — agent must create a human-approval ticket
    - Daily total over $25 (configurable): BLOCKED
    - Monthly total over $200 (configurable): BLOCKED

    When MCP Elicitation is available, expenditures in the $5-$50 tier will
    pause and request admin confirmation inline before proceeding. If the
    client does not support elicitation, the expenditure is auto-approved
    and flagged for daily review (backward compatible behavior).

    Args:
        amount_usd: Amount in USD (e.g. 2.50).
        description: What the spend is for.
        vendor: Who the payment goes to (e.g. "OpenAI", "AWS").
        category: Spending category (default: "api"). Examples: api, hosting, tools, other.

    Returns:
        Confirmation of the recorded transaction, or an error if blocked.
    """
    if amount_usd <= 0:
        return "Error: amount_usd must be a positive number."

    if not description:
        return "Error: description is required."

    if not vendor:
        return "Error: vendor is required."

    try:
        # --- Integrity check: detect log tampering ---
        is_valid, reason = _verify_integrity()
        if not is_valid:
            return json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "integrity_violation",
                    "detail": f"Spending log integrity check failed: {reason}. "
                    "The spending log may have been tampered with. "
                    "All spending is blocked until admin investigates. "
                    "Create a human-approval ticket immediately.",
                },
                indent=2,
            )

        # --- Tier check: over $50 is BLOCKED ---
        if amount_usd > 50:
            _append_log_entry(amount_usd, vendor, category, description, "BLOCKED")
            return json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "amount_exceeds_threshold",
                    "amount_usd": amount_usd,
                    "threshold_usd": 50.00,
                    "action_required": (
                        "This expenditure exceeds the $50.00 auto-approval limit. "
                        "Please create a human-approval ticket with the following details: "
                        f"Amount: ${amount_usd:.2f}, Vendor: {vendor}, "
                        f"Description: {description}, Category: {category}."
                    ),
                },
                indent=2,
            )

        # --- Cap checks ---
        entries = _parse_log_entries()
        totals = _compute_totals(entries)

        # Daily cap
        if totals["daily_spent"] + amount_usd > DAILY_CAP_USD:
            _append_log_entry(amount_usd, vendor, category, description, "BLOCKED-daily-cap")
            return json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "daily_cap_exceeded",
                    "amount_usd": amount_usd,
                    "daily_spent": round(totals["daily_spent"], 2),
                    "daily_cap": DAILY_CAP_USD,
                    "daily_remaining": round(totals["daily_remaining"], 2),
                    "action_required": (
                        f"This expenditure would exceed the daily cap of ${DAILY_CAP_USD:.2f}. "
                        f"Already spent today: ${totals['daily_spent']:.2f}. "
                        f"Remaining: ${totals['daily_remaining']:.2f}. "
                        "Please create a human-approval ticket or wait until tomorrow."
                    ),
                },
                indent=2,
            )

        # Monthly cap
        if totals["monthly_spent"] + amount_usd > MONTHLY_CAP_USD:
            _append_log_entry(amount_usd, vendor, category, description, "BLOCKED-monthly-cap")
            return json.dumps(
                {
                    "status": "BLOCKED",
                    "reason": "monthly_cap_exceeded",
                    "amount_usd": amount_usd,
                    "monthly_spent": round(totals["monthly_spent"], 2),
                    "monthly_cap": MONTHLY_CAP_USD,
                    "monthly_remaining": round(totals["monthly_remaining"], 2),
                    "action_required": (
                        f"This expenditure would exceed the monthly cap of ${MONTHLY_CAP_USD:.2f}. "
                        f"Already spent this month: ${totals['monthly_spent']:.2f}. "
                        f"Remaining: ${totals['monthly_remaining']:.2f}. "
                        "Please create a human-approval ticket."
                    ),
                },
                indent=2,
            )

        # --- Tier determination + elicitation for $5-$50 ---
        if amount_usd < 5:
            status = "approved"
            tier_label = "auto-approved (under $5)"
            elicitation_used = False
        else:
            # $5-$50 tier: attempt inline elicitation confirmation
            if ctx is not None:
                approved, notes = await _elicit_spend_approval(
                    ctx=ctx,
                    amount_usd=amount_usd,
                    vendor=vendor,
                    description=description,
                    category=category,
                    daily_spent=totals["daily_spent"],
                    daily_remaining=totals["daily_remaining"],
                )

                if notes == "elicitation-unavailable":
                    # Client doesn't support elicitation — fall back
                    status = "flagged-for-review"
                    tier_label = "auto-approved, flagged for daily review ($5-$50, no elicitation)"
                    elicitation_used = False
                elif not approved:
                    # Admin explicitly rejected via elicitation
                    reject_reason = notes or "rejected via elicitation"
                    _append_log_entry(
                        amount_usd, vendor, category, description,
                        f"REJECTED-elicitation: {reject_reason}",
                    )
                    return json.dumps(
                        {
                            "status": "REJECTED",
                            "reason": "admin_rejected_via_elicitation",
                            "amount_usd": amount_usd,
                            "vendor": vendor,
                            "category": category,
                            "description": description,
                            "admin_notes": reject_reason,
                            "action": "Expenditure was rejected by admin via inline confirmation.",
                        },
                        indent=2,
                    )
                else:
                    # Admin approved via elicitation
                    status = "approved-elicitation"
                    tier_label = "admin-approved via elicitation ($5-$50)"
                    elicitation_used = True
            else:
                # No context available — fall back to legacy behavior
                status = "flagged-for-review"
                tier_label = "auto-approved, flagged for daily review ($5-$50)"
                elicitation_used = False

        # --- Record the transaction ---
        _append_log_entry(amount_usd, vendor, category, description, status)

        # Refresh totals after recording
        entries = _parse_log_entries()
        new_totals = _compute_totals(entries)

        result = {
            "status": status,
            "tier": tier_label,
            "amount_usd": amount_usd,
            "vendor": vendor,
            "category": category,
            "description": description,
            "elicitation_used": elicitation_used,
            "daily_spent_after": round(new_totals["daily_spent"], 2),
            "daily_remaining_after": round(new_totals["daily_remaining"], 2),
            "monthly_spent_after": round(new_totals["monthly_spent"], 2),
            "monthly_remaining_after": round(new_totals["monthly_remaining"], 2),
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return f"Error: Failed to record expenditure — {e}"


@mcp.tool()
async def get_spending_log(days: int = 7) -> str:
    """Get recent spending transactions.

    Args:
        days: Number of days of history to return (default: 7).

    Returns:
        Formatted list of recent spending transactions.
    """
    days = max(1, min(days, 365))

    try:
        entries = _parse_log_entries()

        if not entries:
            return "No spending transactions recorded yet."

        # Filter by date range
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        filtered = []
        for entry in entries:
            ts = entry.get("timestamp", "")
            # Simple string comparison works because timestamps are ISO-formatted
            if ts >= cutoff_str:
                filtered.append(entry)

        if not filtered:
            return f"No spending transactions found in the last {days} day(s)."

        # Compute summary stats
        total_approved = sum(
            e["amount_usd"]
            for e in filtered
            if e["status"] in ("approved", "flagged-for-review", "approved-elicitation")
        )
        total_blocked = sum(
            e["amount_usd"]
            for e in filtered
            if e["status"].startswith("BLOCKED")
        )

        result = {
            "period": f"Last {days} day(s)",
            "total_transactions": len(filtered),
            "total_approved_usd": round(total_approved, 2),
            "total_blocked_usd": round(total_blocked, 2),
            "transactions": filtered,
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return f"Error: Failed to retrieve spending log — {e}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
