#!/usr/bin/env python3
"""
Resolve the applicable creative brief stack for a project / phase / ticket.

The creative-brief system is hierarchical:
- project briefs define the master contract
- phase briefs add phase-specific proof/review constraints
- ticket briefs add narrow ticket-specific supplements

Resolution order is therefore:
    project -> phase -> ticket

More specific briefs supplement or override the less specific ones, but they do
not replace the project brief entirely.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_ticket_evidence import parse_frontmatter_map

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
TICKET_ID_RE = re.compile(r"\bT-\d+\b", re.IGNORECASE)


@dataclass
class BriefRecord:
    path: str
    scope: str
    title: str
    project: str
    phase: int | None
    phase_title: str | None
    ticket: str | None
    applies_to_tickets: list[str]
    covered_waves: list[str]
    brief_scope_raw: str
    captured: str | None
    updated: str | None


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", help="Project slug.")
    parser.add_argument("--project-file", help="Optional project markdown path.")
    parser.add_argument("--project-plan", help="Optional project plan snapshot path.")
    parser.add_argument("--phase", type=int, help="Phase number to resolve a phase brief for.")
    parser.add_argument("--wave", help="Optional active wave name for capability-wave brief resolution.")
    parser.add_argument("--ticket-id", help="Ticket ID to resolve ticket-specific briefs for.")
    parser.add_argument("--ticket-path", help="Optional ticket markdown path (used to infer ticket ID).")
    parser.add_argument(
        "--search-root",
        action="append",
        default=[],
        help="Root directory to scan for creative-brief snapshots. May be repeated.",
    )
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--markdown-out", help="Optional markdown output path.")
    return parser.parse_args()


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def normalize_project(value: object) -> str:
    return normalize_text(value)


def normalize_ticket(value: object) -> str | None:
    text = normalize_text(value).upper()
    return text or None


def parse_timestamp(value: object) -> datetime | None:
    text = normalize_text(value)
    if not text:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)", text)
    if not match:
        return None
    try:
        return datetime.fromisoformat(match.group(1))
    except ValueError:
        return None


def render_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def parse_phase(value: object) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_ticket_list(value: object) -> list[str]:
    if isinstance(value, list):
        raw = " ".join(str(item) for item in value)
    else:
        raw = normalize_text(value)
    return sorted({match.group(0).upper() for match in TICKET_ID_RE.finditer(raw)})


WAVE_LABEL_RE = re.compile(r"\bwave\s+(\d+[a-z]?)\b", re.IGNORECASE)
COVERAGE_KEYWORDS = (
    "primary scope",
    "covers",
    "covering",
    "applies to",
    "governs",
    "active wave",
    "active, this brief",
)


def normalize_wave_label(value: object) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    upper = text.upper()
    if upper in {"ALL", "ALL WAVES", "ENTIRE PHASE", "WHOLE PHASE"}:
        return "ALL"
    match = WAVE_LABEL_RE.search(text)
    if match:
        return f"Wave {match.group(1).upper()}"
    if re.fullmatch(r"\d+[A-Za-z]?", text):
        return f"Wave {text.upper()}"
    return text


def extract_wave_labels(text: str) -> list[str]:
    labels = {f"Wave {match.group(1).upper()}" for match in WAVE_LABEL_RE.finditer(text or "")}
    return sorted(labels)


def extract_wave_coverage_labels(*texts: str) -> list[str]:
    labels: set[str] = set()
    for text in texts:
        if not text:
            continue
        for line in text.splitlines():
            lower = line.lower()
            if not any(keyword in lower for keyword in COVERAGE_KEYWORDS):
                continue
            labels.update(extract_wave_labels(line))
    return sorted(labels)


def parse_wave_list(value: object) -> list[str]:
    if isinstance(value, list):
        raw_values = [str(item) for item in value]
    else:
        raw_text = normalize_text(value)
        raw_values = [raw_text] if raw_text else []

    parsed: set[str] = set()
    for raw in raw_values:
        normalized = normalize_wave_label(raw)
        if normalized == "ALL":
            parsed.add("ALL")
            continue
        parsed.update(extract_wave_labels(raw))
        if normalized and normalized.startswith("Wave "):
            parsed.add(normalized)
    return sorted(parsed)


def classify_scope(frontmatter: dict) -> tuple[str, str]:
    raw_scope = normalize_text(frontmatter.get("brief_scope")).lower()
    if raw_scope in {"project", "phase", "ticket"}:
        return raw_scope, raw_scope
    if normalize_text(frontmatter.get("ticket")):
        return "ticket", raw_scope
    if frontmatter.get("phase_number") is not None or frontmatter.get("phase") is not None:
        return "phase", raw_scope
    return "project", raw_scope


def is_creative_brief(path: Path, frontmatter: dict) -> bool:
    subtype = normalize_text(frontmatter.get("subtype")).lower()
    if subtype == "brief-review":
        return False
    title = normalize_text(frontmatter.get("title")).lower()
    tags = normalize_text(frontmatter.get("tags")).lower()
    return (
        subtype == "creative-brief"
        or "creative brief" in title
        or "creative-brief" in path.name.lower()
        or "creative-brief" in tags
    )


def infer_project(args: argparse.Namespace) -> str:
    if args.project:
        return normalize_project(args.project)
    if args.project_file:
        path = Path(args.project_file).expanduser().resolve()
        frontmatter = parse_frontmatter_map(path)
        explicit = normalize_project(frontmatter.get("project"))
        if explicit:
            return explicit
        return path.stem
    if args.project_plan:
        path = Path(args.project_plan).expanduser().resolve()
        frontmatter = parse_frontmatter_map(path)
        explicit = normalize_project(frontmatter.get("project"))
        if explicit:
            return explicit
        stem = path.stem
        stem = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", stem)
        stem = re.sub(r"^(creative-brief|project-plan)-", "", stem)
        return stem
    raise SystemExit("resolve_briefs.py requires --project, --project-file, or --project-plan")


def infer_ticket_id(args: argparse.Namespace) -> str | None:
    if args.ticket_id:
        return normalize_ticket(args.ticket_id)
    if args.ticket_path:
        path = Path(args.ticket_path).expanduser().resolve()
        frontmatter = parse_frontmatter_map(path)
        explicit = normalize_ticket(frontmatter.get("id"))
        if explicit:
            return explicit
        match = TICKET_ID_RE.search(path.stem.upper())
        if match:
            return match.group(0).upper()
    return None


def infer_search_roots(args: argparse.Namespace) -> list[Path]:
    roots = [Path(raw).expanduser().resolve() for raw in args.search_root]
    if roots:
        return roots

    inferred: list[Path] = []
    for raw_path in (args.project_file, args.project_plan):
        if not raw_path:
            continue
        path = Path(raw_path).expanduser().resolve()
        if path.parent.name == "projects":
            inferred.append((path.parent.parent / "snapshots").resolve())
        elif path.parent.name == "snapshots":
            inferred.append(path.parent.resolve())

    cwd = Path.cwd()
    client_snapshots = cwd / "vault" / "clients"
    if client_snapshots.exists():
        for candidate in client_snapshots.glob("*/snapshots"):
            inferred.append(candidate.resolve())
    root_snapshots = cwd / "vault" / "snapshots"
    if root_snapshots.exists():
        inferred.append(root_snapshots.resolve())

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in inferred:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def build_record(path: Path, frontmatter: dict) -> BriefRecord:
    scope, raw_scope = classify_scope(frontmatter)
    captured = parse_timestamp(frontmatter.get("captured") or frontmatter.get("created"))
    updated = parse_timestamp(frontmatter.get("updated")) or captured
    covered_waves = parse_wave_list(frontmatter.get("covered_waves"))
    if scope == "phase" and not covered_waves:
        brief_text = path.read_text(encoding="utf-8")
        covered_waves = sorted(
            {
                *extract_wave_labels(normalize_text(frontmatter.get("title"))),
                *extract_wave_coverage_labels(brief_text),
            }
        )
    return BriefRecord(
        path=str(path.resolve()),
        scope=scope,
        title=normalize_text(frontmatter.get("title")) or path.stem,
        project=normalize_project(frontmatter.get("project")),
        phase=parse_phase(frontmatter.get("phase_number") or frontmatter.get("phase")),
        phase_title=normalize_text(frontmatter.get("phase_title")) or None,
        ticket=normalize_ticket(frontmatter.get("ticket")),
        applies_to_tickets=parse_ticket_list(frontmatter.get("applies_to_tickets")),
        covered_waves=covered_waves,
        brief_scope_raw=raw_scope,
        captured=render_timestamp(captured),
        updated=render_timestamp(updated),
    )


def brief_sort_key(record: BriefRecord) -> tuple[datetime, datetime, str]:
    updated = parse_timestamp(record.updated) or datetime.min
    captured = parse_timestamp(record.captured) or datetime.min
    return (updated, captured, record.path)


def scan_briefs(search_roots: list[Path], project: str) -> list[BriefRecord]:
    matches: list[BriefRecord] = []
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if not path.is_file():
                continue
            frontmatter = parse_frontmatter_map(path)
            if not is_creative_brief(path, frontmatter):
                continue
            if normalize_project(frontmatter.get("project")) != project:
                continue
            matches.append(build_record(path, frontmatter))
    return sorted(matches, key=brief_sort_key, reverse=True)


def matches_phase(record: BriefRecord, phase: int | None) -> bool:
    return record.scope == "phase" and phase is not None and record.phase == phase


def phase_brief_covers_wave(record: BriefRecord, wave: object) -> bool:
    if record.scope != "phase":
        return False
    normalized_wave = normalize_wave_label(wave)
    if normalized_wave is None:
        return True
    if not record.covered_waves:
        return True
    if "ALL" in record.covered_waves:
        return True
    return normalized_wave in record.covered_waves


def matches_ticket(record: BriefRecord, ticket_id: str | None) -> bool:
    if ticket_id is None:
        return False
    if record.ticket == ticket_id:
        return True
    if record.scope == "ticket" and ticket_id in record.applies_to_tickets:
        return True
    return False


def dedupe_by_path(records: list[BriefRecord]) -> list[BriefRecord]:
    deduped: list[BriefRecord] = []
    seen: set[str] = set()
    for record in records:
        if record.path in seen:
            continue
        seen.add(record.path)
        deduped.append(record)
    return deduped


def select_primary(records: list[BriefRecord]) -> BriefRecord | None:
    if not records:
        return None
    return sorted(records, key=brief_sort_key, reverse=True)[0]


def build_report(args: argparse.Namespace) -> dict:
    project = infer_project(args)
    ticket_id = infer_ticket_id(args)
    search_roots = infer_search_roots(args)
    wave = normalize_wave_label(getattr(args, "wave", None))
    scanned = scan_briefs(search_roots, project)

    project_briefs = dedupe_by_path([record for record in scanned if record.scope == "project"])
    phase_briefs = dedupe_by_path(
        [record for record in scanned if matches_phase(record, args.phase) and phase_brief_covers_wave(record, wave)]
    )
    ticket_briefs = dedupe_by_path([record for record in scanned if matches_ticket(record, ticket_id)])

    ordered = [
        record
        for record in (
            select_primary(project_briefs),
            select_primary(phase_briefs),
            select_primary(ticket_briefs),
        )
        if record is not None
    ]

    issues: list[str] = []
    if not project_briefs and (phase_briefs or ticket_briefs):
        issues.append("missing_project_brief")
    if phase_briefs and not project_briefs:
        issues.append("phase_brief_without_project_brief")
    if ticket_briefs and not project_briefs:
        issues.append("ticket_brief_without_project_brief")

    integrity_checks = {
        "has_project_brief": bool(project_briefs),
        "has_phase_brief": bool(phase_briefs),
        "has_ticket_brief": bool(ticket_briefs),
        "missing_project_brief": "missing_project_brief" in issues,
        "phase_brief_without_project_brief": "phase_brief_without_project_brief" in issues,
        "ticket_brief_without_project_brief": "ticket_brief_without_project_brief" in issues,
    }

    return {
        "generated_at": now(),
        "project": project,
        "phase": args.phase,
        "wave": wave,
        "ticket_id": ticket_id,
        "search_roots": [str(path) for path in search_roots],
        "precedence": {
            "read_order": ["project", "phase", "ticket"],
            "conflict_rule": "More specific briefs narrow or override broader briefs on conflict.",
        },
        "integrity_checks": integrity_checks,
        "issues": issues,
        "project_briefs": [asdict(record) for record in project_briefs],
        "phase_briefs": [asdict(record) for record in phase_briefs],
        "ticket_briefs": [asdict(record) for record in ticket_briefs],
        "ordered_briefs": [asdict(record) for record in ordered],
    }


def render_markdown(report: dict) -> str:
    lines = [
        f"# Brief Resolution — {report['project']}",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Phase: {report['phase'] if report['phase'] is not None else 'N/A'}",
        f"- Wave: {report.get('wave') or 'N/A'}",
        f"- Ticket: {report['ticket_id'] or 'N/A'}",
        f"- Read order: {' -> '.join(report['precedence']['read_order'])}",
        f"- Conflict rule: {report['precedence']['conflict_rule']}",
        "",
    ]
    issues = report.get("issues") or []
    if issues:
        lines.extend(
            [
                "## Integrity Checks",
                "",
                f"- Issues: {', '.join(issues)}",
                "- A project-scoped brief is the required root contract. Phase/ticket briefs are supplements only.",
                "",
            ]
        )
    lines.extend(
        [
        "## Ordered Brief Stack",
        "",
        ]
    )
    ordered = report["ordered_briefs"]
    if not ordered:
        lines.append("- No applicable creative briefs found.")
    else:
        for entry in ordered:
            lines.append(
                f"- `{entry['scope']}` — `{entry['title']}` → `{entry['path']}`"
            )

    for key, heading in (
        ("project_briefs", "Project Briefs"),
        ("phase_briefs", "Phase Briefs"),
        ("ticket_briefs", "Ticket Briefs"),
    ):
        lines.extend(["", f"## {heading}", ""])
        entries = report[key]
        if not entries:
            lines.append("- None")
            continue
        for entry in entries:
            detail_bits = []
            if entry.get("phase") is not None:
                detail_bits.append(f"phase {entry['phase']}")
            if entry.get("ticket"):
                detail_bits.append(f"ticket {entry['ticket']}")
            if entry.get("applies_to_tickets"):
                detail_bits.append(
                    "applies_to=" + ",".join(entry["applies_to_tickets"])
                )
            if entry.get("covered_waves"):
                detail_bits.append("covered_waves=" + ",".join(entry["covered_waves"]))
            detail_text = f" ({'; '.join(detail_bits)})" if detail_bits else ""
            lines.append(f"- `{entry['title']}`{detail_text} → `{entry['path']}`")
    return "\n".join(lines).rstrip() + "\n"


def write_output(path: str | None, content: str) -> None:
    if not path:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = build_report(args)
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown_text = render_markdown(report)
    write_output(args.json_out, json_text)
    write_output(args.markdown_out, markdown_text)
    if not args.json_out and not args.markdown_out:
        sys.stdout.write(json_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
