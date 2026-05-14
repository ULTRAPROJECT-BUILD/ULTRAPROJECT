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

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import jsonschema
from pydantic import BaseModel, Field

try:
    from mcp.server.fastmcp import Context, FastMCP
except ModuleNotFoundError:  # Keep tests and direct smoke checks usable before MCP deps are installed.
    Context = Any  # type: ignore[assignment]

    class FastMCP:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def tool(self):
            def decorator(func):
                return func

            return decorator

        def run(self) -> None:
            raise RuntimeError("mcp package is not installed; run pip install -r requirements.txt")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SPENDING_LOG_PATH = os.environ.get(
    "SPENDING_LOG_PATH", "vault/config/spending-log.md"
)
SPENDING_RESERVATION_LOG_PATH = os.environ.get("SPENDING_RESERVATION_LOG_PATH")
DAILY_CAP_USD = float(os.environ.get("DAILY_CAP_USD", "25"))
MONTHLY_CAP_USD = float(os.environ.get("MONTHLY_CAP_USD", "200"))
VALID_RESERVATION_CATEGORIES = {"tool_acquisition", "tool_usage", "api_call", "other"}

# Resolve relative paths against the working directory
_log_path = Path(SPENDING_LOG_PATH)
if not _log_path.is_absolute():
    _log_path = Path.cwd() / _log_path
SPENDING_LOG_FILE = _log_path
if SPENDING_RESERVATION_LOG_PATH:
    _reservation_log_path = Path(SPENDING_RESERVATION_LOG_PATH)
    if not _reservation_log_path.is_absolute():
        _reservation_log_path = Path.cwd() / _reservation_log_path
    SPENDING_RESERVATION_LOG_FILE = _reservation_log_path
else:
    SPENDING_RESERVATION_LOG_FILE = SPENDING_LOG_FILE.with_suffix(".reservations.json")

REPO_ROOT = Path(__file__).resolve().parents[5]
SPENDING_RESERVATION_SCHEMA_PATH = REPO_ROOT / "schemas" / "spending-reservation.schema.json"
_QUOTE_CACHE: dict[str, dict[str, Any]] = {}

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
    integrity_file.parent.mkdir(parents=True, exist_ok=True)
    integrity_file.write_text(
        f"{file_hash}\n{entry_count}\n",
        encoding="utf-8",
    )


def _verify_integrity() -> tuple[bool, str]:
    """Verify spending log has not been tampered with.

    Returns (is_valid, reason). If the integrity file doesn't exist yet,
    initializes it and returns valid (first-run case).
    """
    _ensure_log_exists()
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_text() -> str:
    return _utc_now().isoformat()


def _reservation_schema() -> dict[str, Any]:
    return json.loads(SPENDING_RESERVATION_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate_reservation_record(record: dict[str, Any]) -> None:
    jsonschema.Draft7Validator(_reservation_schema()).validate(record)


def _ensure_reservation_log_exists() -> None:
    SPENDING_RESERVATION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SPENDING_RESERVATION_LOG_FILE.exists():
        SPENDING_RESERVATION_LOG_FILE.write_text("[]\n", encoding="utf-8")


def _read_reservation_records() -> list[dict[str, Any]]:
    _ensure_reservation_log_exists()
    try:
        data = json.loads(SPENDING_RESERVATION_LOG_FILE.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"reservation log is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("reservation log must contain a JSON array")
    for record in data:
        if isinstance(record, dict):
            _validate_reservation_record(record)
        else:
            raise ValueError("reservation log contains a non-object record")
    return data


def _write_reservation_records(records: list[dict[str, Any]]) -> None:
    for record in records:
        _validate_reservation_record(record)
    _ensure_reservation_log_exists()
    SPENDING_RESERVATION_LOG_FILE.write_text(
        json.dumps(records, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _find_reservation(records: list[dict[str, Any]], reservation_id: str) -> dict[str, Any] | None:
    for record in records:
        if record.get("reservation_id") == reservation_id:
            return record
    return None


def _active_reservation_total(records: list[dict[str, Any]]) -> float:
    return round(
        sum(float(record.get("reserved_amount_usd") or record.get("amount_usd") or 0) for record in records if record.get("state") == "reserved"),
        2,
    )


def _expire_reservations(records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    loaded = records if records is not None else _read_reservation_records()
    changed = False
    now_dt = _utc_now()
    for record in loaded:
        if record.get("state") != "reserved" or not record.get("expires_at"):
            continue
        expires_at = datetime.fromisoformat(str(record["expires_at"]).replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now_dt:
            record["state"] = "expired"
            record["actual_amount_usd"] = 0
            record["updated_at"] = _utc_now_text()
            record["expired_at"] = record["updated_at"]
            record["reason"] = "reservation expired before capture"
            changed = True
            _append_log_entry(
                0,
                record["vendor"],
                record["category"],
                f"Reservation expired: {record.get('reservation_id')}",
                "expired",
            )
    if changed:
        _write_reservation_records(loaded)
    return loaded


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
        if status not in ("approved", "flagged-for-review", "approved-elicitation", "captured"):
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


def _spending_projection(amount_usd: float) -> dict[str, Any]:
    entries = _parse_log_entries()
    totals = _compute_totals(entries)
    reservations = _expire_reservations()
    active_reserved = _active_reservation_total(reservations)
    projected_daily = totals["daily_spent"] + active_reserved + amount_usd
    projected_monthly = totals["monthly_spent"] + active_reserved + amount_usd
    return {
        "daily_spent": round(totals["daily_spent"], 2),
        "monthly_spent": round(totals["monthly_spent"], 2),
        "active_reserved_usd": active_reserved,
        "projected_daily_total_usd": round(projected_daily, 2),
        "projected_monthly_total_usd": round(projected_monthly, 2),
        "projected_daily_remaining_usd": round(DAILY_CAP_USD - projected_daily, 2),
        "projected_monthly_remaining_usd": round(MONTHLY_CAP_USD - projected_monthly, 2),
        "daily_cap_usd": DAILY_CAP_USD,
        "monthly_cap_usd": MONTHLY_CAP_USD,
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
        reservations = _expire_reservations()
        active_reserved = _active_reservation_total(reservations)

        result = {
            "daily_cap_usd": DAILY_CAP_USD,
            "daily_spent_usd": round(totals["daily_spent"], 2),
            "daily_remaining_usd": round(totals["daily_remaining"], 2),
            "monthly_cap_usd": MONTHLY_CAP_USD,
            "monthly_spent_usd": round(totals["monthly_spent"], 2),
            "monthly_remaining_usd": round(totals["monthly_remaining"], 2),
            "active_reserved_usd": active_reserved,
            "daily_projected_remaining_with_reservations_usd": round(
                DAILY_CAP_USD - totals["daily_spent"] - active_reserved,
                2,
            ),
            "monthly_projected_remaining_with_reservations_usd": round(
                MONTHLY_CAP_USD - totals["monthly_spent"] - active_reserved,
                2,
            ),
            "log_file": str(SPENDING_LOG_FILE),
            "reservation_log_file": str(SPENDING_RESERVATION_LOG_FILE),
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
async def quote_spend(
    project_slug: str,
    vendor: str,
    amount_usd: float,
    recurrence: str,
    category: str,
    requested_by_tool_stack: str = "",
) -> str:
    """Pre-flight a spend request without recording a transaction.

    The quote checks daily/monthly caps plus active reservations. It records
    nothing; the returned quote_id is held only in server memory until reserve.
    """
    if amount_usd <= 0:
        return json.dumps({"status": "REJECTED", "reason": "amount_usd must be positive"}, indent=2)
    if category not in VALID_RESERVATION_CATEGORIES:
        return json.dumps(
            {
                "status": "REJECTED",
                "reason": "invalid_category",
                "valid_categories": sorted(VALID_RESERVATION_CATEGORIES),
            },
            indent=2,
        )
    if recurrence not in {"none", "one_time", "monthly", "annual"}:
        return json.dumps({"status": "REJECTED", "reason": "invalid_recurrence"}, indent=2)
    if not project_slug or not vendor:
        return json.dumps({"status": "REJECTED", "reason": "project_slug and vendor are required"}, indent=2)

    try:
        is_valid, reason = _verify_integrity()
        if not is_valid:
            return json.dumps(
                {
                    "status": "REJECTED",
                    "reason": "integrity_violation",
                    "detail": reason,
                },
                indent=2,
            )
        projection = _spending_projection(amount_usd)
        cap_reason = None
        if projection["projected_daily_total_usd"] > DAILY_CAP_USD:
            cap_reason = "daily_cap_exceeded"
            cap = DAILY_CAP_USD
        elif projection["projected_monthly_total_usd"] > MONTHLY_CAP_USD:
            cap_reason = "monthly_cap_exceeded"
            cap = MONTHLY_CAP_USD
        else:
            cap = None

        quote_id = f"quote-{uuid.uuid4()}"
        quote = {
            "quote_id": quote_id,
            "project_slug": project_slug,
            "vendor": vendor,
            "amount_usd": round(amount_usd, 2),
            "recurrence": recurrence,
            "category": category,
            "requested_by_tool_stack": requested_by_tool_stack or None,
            "created_at": _utc_now_text(),
            "projection": projection,
        }
        _QUOTE_CACHE[quote_id] = quote
        if cap_reason:
            return json.dumps(
                {
                    "status": "REJECTED",
                    "reason": cap_reason,
                    "quote_id": quote_id,
                    "requested_amount_usd": round(amount_usd, 2),
                    "current_cap_usd": cap,
                    "projected_balance_usd": projection[
                        "projected_daily_remaining_usd"
                        if cap_reason == "daily_cap_exceeded"
                        else "projected_monthly_remaining_usd"
                    ],
                    "vendor": vendor,
                    "recurrence": recurrence,
                    "category": category,
                    "requested_by_tool_stack": requested_by_tool_stack,
                    "projection": projection,
                },
                indent=2,
            )
        return json.dumps(
            {
                "status": "OK",
                "quote_id": quote_id,
                "projected_balance": projection,
                "projected_daily_remaining_usd": projection["projected_daily_remaining_usd"],
                "projected_monthly_remaining_usd": projection["projected_monthly_remaining_usd"],
            },
            indent=2,
        )
    except Exception as e:
        return f"Error: Failed to quote spend — {e}"


@mcp.tool()
async def reserve_spend(
    quote_id: str,
    authorization_id: str,
    expires_at: str,
    project_slug: str = "",
    category: str = "",
    max_authorized_amount_usd: float | None = None,
) -> str:
    """Create a wallet hold from a prior quote and OAI authorization."""
    if not quote_id or not authorization_id or not expires_at:
        return json.dumps(
            {"status": "REJECTED", "reason": "quote_id, authorization_id, and expires_at are required"},
            indent=2,
        )
    quote = _QUOTE_CACHE.get(quote_id)
    if not quote:
        return json.dumps({"status": "REJECTED", "reason": "unknown_or_expired_quote_id"}, indent=2)
    if project_slug and project_slug != quote["project_slug"]:
        return json.dumps({"status": "REJECTED", "reason": "project_slug_mismatch"}, indent=2)
    if category and category != quote["category"]:
        return json.dumps({"status": "REJECTED", "reason": "category_mismatch"}, indent=2)
    if max_authorized_amount_usd is not None and quote["amount_usd"] > max_authorized_amount_usd:
        return json.dumps(
            {
                "status": "REJECTED",
                "reason": "quote_exceeds_authorization",
                "quote_amount_usd": quote["amount_usd"],
                "max_authorized_amount_usd": max_authorized_amount_usd,
            },
            indent=2,
        )

    try:
        is_valid, reason = _verify_integrity()
        if not is_valid:
            return json.dumps({"status": "REJECTED", "reason": "integrity_violation", "detail": reason}, indent=2)
        records = _expire_reservations()
        for record in records:
            if record.get("quote_id") == quote_id and record.get("authorization_id") == authorization_id:
                return json.dumps({"status": "OK", "reservation": record}, indent=2)

        projection = _spending_projection(float(quote["amount_usd"]))
        if projection["projected_daily_total_usd"] > DAILY_CAP_USD:
            return json.dumps(
                {
                    "status": "REJECTED",
                    "reason": "daily_cap_exceeded",
                    "projected_balance": projection,
                },
                indent=2,
            )
        if projection["projected_monthly_total_usd"] > MONTHLY_CAP_USD:
            return json.dumps(
                {
                    "status": "REJECTED",
                    "reason": "monthly_cap_exceeded",
                    "projected_balance": projection,
                },
                indent=2,
            )

        reservation_id = f"res-{uuid.uuid4()}"
        now_text = _utc_now_text()
        record = {
            "record_type": "reservation",
            "state": "reserved",
            "quote_id": quote_id,
            "reservation_id": reservation_id,
            "capture_id": None,
            "release_id": None,
            "project_slug": quote["project_slug"],
            "vendor": quote["vendor"],
            "category": quote["category"],
            "recurrence": quote["recurrence"],
            "amount_usd": float(quote["amount_usd"]),
            "reserved_amount_usd": float(quote["amount_usd"]),
            "actual_amount_usd": None,
            "authorization_id": authorization_id,
            "requested_by_tool_stack": quote.get("requested_by_tool_stack"),
            "expires_at": expires_at,
            "receipt_ref": None,
            "reason": None,
            "created_at": now_text,
            "updated_at": now_text,
            "captured_at": None,
            "released_at": None,
            "expired_at": None,
        }
        records.append(record)
        _write_reservation_records(records)
        _append_log_entry(
            float(quote["amount_usd"]),
            quote["vendor"],
            quote["category"],
            f"Reserved spend {reservation_id} from {quote_id} authorization {authorization_id}",
            "reserved",
        )
        return json.dumps({"status": "OK", "reservation": record}, indent=2)
    except Exception as e:
        return f"Error: Failed to reserve spend — {e}"


@mcp.tool()
async def capture_spend(
    reservation_id: str,
    actual_amount_usd: float,
    receipt_ref: str,
    project_slug: str = "",
    category: str = "",
) -> str:
    """Convert a reservation into captured spend. Repeated captures are idempotent."""
    if actual_amount_usd < 0:
        return json.dumps({"status": "REJECTED", "reason": "actual_amount_usd must be non-negative"}, indent=2)
    if not reservation_id or not receipt_ref:
        return json.dumps({"status": "REJECTED", "reason": "reservation_id and receipt_ref are required"}, indent=2)
    try:
        is_valid, reason = _verify_integrity()
        if not is_valid:
            return json.dumps({"status": "REJECTED", "reason": "integrity_violation", "detail": reason}, indent=2)
        records = _expire_reservations()
        record = _find_reservation(records, reservation_id)
        if not record:
            return json.dumps({"status": "REJECTED", "reason": "unknown_reservation_id"}, indent=2)
        if project_slug and project_slug != record["project_slug"]:
            return json.dumps({"status": "REJECTED", "reason": "project_slug_mismatch"}, indent=2)
        if category and category != record["category"]:
            return json.dumps({"status": "REJECTED", "reason": "category_mismatch"}, indent=2)
        if record["state"] == "captured":
            return json.dumps({"status": "OK", "capture": record, "idempotent": True}, indent=2)
        if record["state"] in {"released", "expired"}:
            return json.dumps({"status": "REJECTED", "reason": f"reservation_is_{record['state']}"}, indent=2)
        reserved = float(record.get("reserved_amount_usd") or record.get("amount_usd") or 0)
        if actual_amount_usd > reserved:
            return json.dumps(
                {
                    "status": "REJECTED",
                    "reason": "actual_exceeds_reserved",
                    "reserved_amount_usd": reserved,
                    "actual_amount_usd": actual_amount_usd,
                },
                indent=2,
            )
        now_text = _utc_now_text()
        record["state"] = "captured"
        record["record_type"] = "capture"
        record["capture_id"] = f"cap-{uuid.uuid4()}"
        record["actual_amount_usd"] = round(actual_amount_usd, 2)
        record["receipt_ref"] = receipt_ref
        record["updated_at"] = now_text
        record["captured_at"] = now_text
        _write_reservation_records(records)
        _append_log_entry(
            actual_amount_usd,
            record["vendor"],
            record["category"],
            f"Captured reservation {reservation_id}; receipt {receipt_ref}; authorization {record['authorization_id']}",
            "captured",
        )
        return json.dumps({"status": "OK", "capture": record, "idempotent": False}, indent=2)
    except Exception as e:
        return f"Error: Failed to capture spend — {e}"


@mcp.tool()
async def release_reservation(
    reservation_id: str,
    reason: str,
    project_slug: str = "",
    category: str = "",
) -> str:
    """Release an unused reservation. Repeated releases are idempotent."""
    if not reservation_id or not reason:
        return json.dumps({"status": "REJECTED", "reason": "reservation_id and reason are required"}, indent=2)
    try:
        is_valid, integrity_reason = _verify_integrity()
        if not is_valid:
            return json.dumps(
                {"status": "REJECTED", "reason": "integrity_violation", "detail": integrity_reason},
                indent=2,
            )
        records = _expire_reservations()
        record = _find_reservation(records, reservation_id)
        if not record:
            return json.dumps({"status": "REJECTED", "reason": "unknown_reservation_id"}, indent=2)
        if project_slug and project_slug != record["project_slug"]:
            return json.dumps({"status": "REJECTED", "reason": "project_slug_mismatch"}, indent=2)
        if category and category != record["category"]:
            return json.dumps({"status": "REJECTED", "reason": "category_mismatch"}, indent=2)
        if record["state"] == "captured":
            return json.dumps({"status": "REJECTED", "reason": "reservation_already_captured"}, indent=2)
        if record["state"] in {"released", "expired"}:
            return json.dumps({"status": "OK", "release": record, "idempotent": True}, indent=2)
        now_text = _utc_now_text()
        record["state"] = "released"
        record["record_type"] = "release"
        record["release_id"] = f"rel-{uuid.uuid4()}"
        record["actual_amount_usd"] = 0
        record["reason"] = reason
        record["updated_at"] = now_text
        record["released_at"] = now_text
        _write_reservation_records(records)
        _append_log_entry(
            0,
            record["vendor"],
            record["category"],
            f"Released reservation {reservation_id}; reason: {reason}; authorization {record['authorization_id']}",
            "released",
        )
        return json.dumps({"status": "OK", "release": record, "idempotent": False}, indent=2)
    except Exception as e:
        return f"Error: Failed to release reservation — {e}"


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
            if e["status"] in ("approved", "flagged-for-review", "approved-elicitation", "captured")
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
            "reservation_log_file": str(SPENDING_RESERVATION_LOG_FILE),
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
