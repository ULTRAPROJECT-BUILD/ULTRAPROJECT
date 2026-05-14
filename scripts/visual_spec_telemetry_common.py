#!/usr/bin/env python3
"""Shared helpers for Visual Specification telemetry and governance scripts."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
PLATFORM_CONFIG_PATH = REPO_ROOT / "vault" / "config" / "platform.md"
OUTCOME_SCHEMA_PATH = SCHEMA_DIR / "outcome-data.schema.json"
PROPOSAL_SCHEMA_PATH = SCHEMA_DIR / "proposal-frontmatter.schema.json"
REGRESSION_SCHEMA_PATH = SCHEMA_DIR / "regression-report.schema.json"

GRADE_ORDER_DESC = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
GRADE_TO_POINTS = {grade: float(len(GRADE_ORDER_DESC) - index - 1) for index, grade in enumerate(GRADE_ORDER_DESC)}
POINTS_TO_GRADE = {points: grade for grade, points in GRADE_TO_POINTS.items()}

TIMESTAMP_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})(?:[T_](?P<time>\d{2}(?::|-)?\d{2}(?::|-)?\d{2})?(?P<tz>Z|[+-]\d{2}:?\d{2})?)?"
)


class TelemetryError(RuntimeError):
    """Raised when telemetry processing cannot continue safely."""


def utc_now_iso() -> str:
    """Return the current UTC timestamp with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and, optionally, a file."""
    text = json.dumps(data, indent=2, sort_keys=True, default=str) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def split_frontmatter(text: str, path: Path | None = None) -> tuple[str, str]:
    """Split markdown frontmatter from body."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        label = str(path) if path else "markdown text"
        raise ValueError(f"{label} does not start with YAML frontmatter.")
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        label = str(path) if path else "markdown text"
        raise ValueError(f"{label} has no closing YAML frontmatter delimiter.")
    return "".join(lines[1:closing_index]), "".join(lines[closing_index + 1 :])


def load_frontmatter(path: Path) -> dict[str, Any]:
    """Load YAML frontmatter from a markdown file."""
    frontmatter_text, _ = split_frontmatter(path.read_text(encoding="utf-8"), path)
    loaded = yaml.safe_load(frontmatter_text)
    return loaded if isinstance(loaded, dict) else {}


def load_markdown_with_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Return parsed frontmatter and body."""
    frontmatter_text, body = split_frontmatter(path.read_text(encoding="utf-8"), path)
    loaded = yaml.safe_load(frontmatter_text)
    return (loaded if isinstance(loaded, dict) else {}), body


def repo_relative(path: Path) -> str:
    """Return a repository-relative path when possible."""
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract a JSON object from a plain-text response."""
    stripped = text.strip()
    if not stripped:
        raise TelemetryError("subprocess returned no JSON output")
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise TelemetryError("subprocess did not emit a JSON object")
        data = json.loads(match.group(0))
    if isinstance(data, dict):
        if any(key in data for key in ("result", "response", "output", "content")):
            for wrapper in ("result", "response", "output", "content"):
                wrapped = data.get(wrapper)
                if isinstance(wrapped, str):
                    try:
                        nested = extract_json_object(wrapped)
                    except TelemetryError:
                        continue
                    if isinstance(nested, dict):
                        return nested
        return data
    raise TelemetryError("JSON output was not an object")


def read_platform_contract() -> str:
    """Return the raw platform config markdown."""
    if not PLATFORM_CONFIG_PATH.exists():
        return ""
    return PLATFORM_CONFIG_PATH.read_text(encoding="utf-8")


def platform_value(key: str, default: Any = None) -> Any:
    """Read a scalar quality-contract value from platform.md."""
    text = read_platform_contract()
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.+?)\s*$", text)
    if not match:
        return default
    raw = match.group(1).strip()
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw.strip("\"'")


def validate_artifact(artifact_path: Path, schema_path: Path, artifact_type: str | None = None) -> dict[str, Any]:
    """Validate an artifact using scripts/validate_schema.py."""
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from validate_schema import validate_artifact as _validate_artifact  # type: ignore

    return _validate_artifact(artifact_path, schema_path, artifact_type)


def load_validated_outcome(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Load one outcome JSON file after schema validation."""
    validation = validate_artifact(path, OUTCOME_SCHEMA_PATH, "json")
    if not validation.get("valid"):
        return None, validation
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, {"artifact": str(path), "valid": False, "errors": [{"path": "/", "message": str(exc), "schema_path": "/"}]}
    return (loaded if isinstance(loaded, dict) else None), validation


def find_outcome_files(root: Path) -> list[Path]:
    """Return sorted outcome files under a directory."""
    if not root.exists():
        return []
    return sorted(path.resolve() for path in root.rglob("visual-spec-outcome-*.json") if path.is_file())


def parse_timestamp(value: Any) -> datetime | None:
    """Parse a timestamp or date string into UTC."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        try:
            return datetime.strptime(normalized, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_timestamp_from_path(path: Path) -> datetime | None:
    """Infer a timestamp from a path name or fall back to mtime."""
    match = TIMESTAMP_RE.search(path.stem)
    if match:
        date_part = match.group("date")
        time_part = match.group("time")
        tz_part = match.group("tz") or "+00:00"
        if time_part:
            normalized_time = time_part.replace("-", ":")
            if len(normalized_time) == 4:
                normalized_time = f"{normalized_time}:00"
            if len(normalized_time) == 2:
                normalized_time = f"{normalized_time}:00:00"
            if tz_part != "Z" and re.fullmatch(r"[+-]\d{4}", tz_part):
                tz_part = f"{tz_part[:3]}:{tz_part[3:]}"
            return parse_timestamp(f"{date_part}T{normalized_time}{'+00:00' if tz_part == 'Z' else tz_part}")
        return parse_timestamp(date_part)
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """Return inclusive start and exclusive end bounds for YYYY-MM."""
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError(f"Invalid month {month!r}; expected YYYY-MM.")
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def in_window(timestamp: datetime | None, *, start: datetime, end: datetime) -> bool:
    """Return true when timestamp falls inside [start, end)."""
    return timestamp is not None and start <= timestamp < end


def grade_to_points(grade: Any) -> float | None:
    """Convert a grade string into ordinal points."""
    text = str(grade or "").strip().upper()
    if text == "N/A" or not text:
        return None
    return GRADE_TO_POINTS.get(text)


def points_to_grade(value: float | None) -> str:
    """Convert ordinal points back to the nearest grade label."""
    if value is None:
        return "N/A"
    rounded = min(max(round(value), 0), int(max(POINTS_TO_GRADE)))
    return POINTS_TO_GRADE.get(float(rounded), "N/A")


def mean(values: list[float]) -> float | None:
    """Return the arithmetic mean for a non-empty list."""
    if not values:
        return None
    return sum(values) / len(values)


def pct(numerator: int, denominator: int) -> float:
    """Return a percentage rounded to two decimals."""
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100.0, 2)


def acceptance_positive(value: Any) -> bool:
    """Return true when operator acceptance is positive."""
    return str(value or "").strip().lower() in {"accepted", "accepted_with_notes"}


def parse_markdown_table(text: str) -> list[dict[str, str]]:
    """Parse the first markdown table in text into rows."""
    table_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|") and line.strip().endswith("|")]
    if len(table_lines) < 2:
        return []
    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append({header[index]: cells[index] for index in range(len(header))})
    return rows


def load_waiver_log(path: Path) -> list[dict[str, Any]]:
    """Read waiver rows from the markdown log."""
    if not path.exists():
        return []
    rows = parse_markdown_table(path.read_text(encoding="utf-8"))
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "date": row.get("Date", ""),
                "project": row.get("Project", ""),
                "reason_category": row.get("Reason category", ""),
                "operator": row.get("Operator", ""),
                "outcome": row.get("Outcome", ""),
                "timestamp": parse_timestamp(row.get("Date")),
            }
        )
    return normalized


def operator_from_text(frontmatter: dict[str, Any], body: str) -> str | None:
    """Best-effort operator ID extraction from frontmatter or markdown body."""
    for key in ("operator_id", "operator", "approved_by", "operator_session_id"):
        value = str(frontmatter.get(key) or "").strip()
        if value:
            return value
    patterns = (
        r"(?im)^operator(?:\s+id)?\s*:\s*([A-Za-z0-9._:-]+)\s*$",
        r"(?im)^approved by\s*:\s*([A-Za-z0-9._:-]+)\s*$",
        r"(?im)^operator session id\s*:\s*([A-Za-z0-9._:-]+)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return match.group(1).strip()
    return None


def proposal_regression_status(frontmatter: dict[str, Any]) -> str:
    """Extract the proposal regression status from known schema shapes."""
    nested = frontmatter.get("regression_check")
    if isinstance(nested, dict):
        status = str(nested.get("status") or "").strip()
        if status:
            return status
    for key in ("regression_status", "regression_check_result"):
        status = str(frontmatter.get(key) or "").strip()
        if status:
            return status
    return ""


def load_project_records_from_log(path: Path) -> list[dict[str, Any]]:
    """Load dated per-project records from JSON, JSONL, or markdown-table logs."""
    if not path.exists():
        return []
    if path.suffix.lower() == ".json":
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return normalize_project_log_payload(loaded)
    if path.suffix.lower() == ".jsonl":
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.extend(normalize_project_log_payload(json.loads(line)))
        return rows
    return normalize_project_table(parse_markdown_table(path.read_text(encoding="utf-8")))


def normalize_project_log_payload(payload: Any) -> list[dict[str, Any]]:
    """Normalize JSON project log payloads into dated operator records."""
    if isinstance(payload, dict):
        if isinstance(payload.get("projects"), list):
            return normalize_project_log_payload(payload["projects"])
        return [normalize_project_record(payload)] if normalize_project_record(payload) else []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        record = normalize_project_record(item)
        if record:
            rows.append(record)
    return rows


def normalize_project_record(item: Any) -> dict[str, Any] | None:
    """Normalize one JSON-like project record."""
    if not isinstance(item, dict):
        return None
    operator = str(item.get("operator") or item.get("operator_id") or item.get("owner") or "").strip()
    project = str(item.get("project") or item.get("project_slug") or item.get("id") or "").strip()
    timestamp = parse_timestamp(item.get("date") or item.get("created") or item.get("timestamp"))
    if not project and not operator and timestamp is None:
        return None
    return {
        "project": project,
        "operator": operator,
        "timestamp": timestamp,
    }


def normalize_project_table(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Normalize markdown-table project records."""
    normalized: list[dict[str, Any]] = []
    for row in rows:
        operator = row.get("Operator") or row.get("Owner") or row.get("operator") or ""
        project = row.get("Project") or row.get("project") or row.get("ID") or ""
        timestamp = parse_timestamp(row.get("Date") or row.get("Created") or row.get("Timestamp"))
        normalized.append({"project": project.strip(), "operator": operator.strip(), "timestamp": timestamp})
    return normalized


def load_outcomes_with_metadata(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load all valid outcome files plus validation failures."""
    outcomes: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    for path in find_outcome_files(root):
        payload, validation = load_validated_outcome(path)
        if payload is None:
            invalid.append({"path": str(path), "validation": validation})
            continue
        payload["_source_path"] = str(path)
        payload["_source_rel"] = repo_relative(path)
        payload["_timestamp"] = parse_timestamp_from_path(path)
        outcomes.append(payload)
    outcomes.sort(key=lambda item: (item.get("_timestamp") or datetime.min.replace(tzinfo=timezone.utc), str(item.get("project") or "")))
    return outcomes, invalid


def outcome_operator_id(outcome: dict[str, Any]) -> str | None:
    """Best-effort operator identifier extraction from an outcome record."""
    for key in ("operator_id", "operator", "operator_session_id"):
        value = str(outcome.get(key) or "").strip()
        if value:
            return value
    return None


def outcome_primary_reviewer(outcome: dict[str, Any]) -> str | None:
    """Return the first reviewer session for an outcome."""
    reviewers = outcome.get("reviewer_grades")
    if not isinstance(reviewers, list):
        return None
    for item in reviewers:
        if not isinstance(item, dict):
            continue
        value = str(item.get("reviewer_session_id") or "").strip()
        if value:
            return value
    return None


def last_ninety_days_start() -> datetime:
    """Convenience helper for 90-day windows."""
    return datetime.now(timezone.utc) - timedelta(days=90)
