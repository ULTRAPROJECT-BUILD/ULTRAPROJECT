#!/usr/bin/env python3
"""
Mechanically verify that a creative-brief ticket has a fresh passing brief gate.

This closes a real orchestration gap: a `creative_brief` ticket can be `closed`
in frontmatter while still lacking the required Codex brief review. Downstream
tickets must not treat that brief as a resolved dependency until a matching
brief-review snapshot both:

1. passes the required threshold, and
2. postdates the brief ticket's latest `updated` timestamp.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_ticket_evidence import parse_frontmatter_map
from resolve_briefs import BriefRecord, brief_sort_key, matches_phase, matches_ticket, parse_timestamp, scan_briefs

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
GRADE_ORDER = ["F", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+"]
GRADE_RANK = {grade: idx for idx, grade in enumerate(GRADE_ORDER)}
HEX_LITERAL_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
PIXEL_LITERAL_RE = re.compile(r"\b\d+(?:\.\d+)?px\b", re.IGNORECASE)


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def normalize_text(value: object) -> str:
    return str(value or "").strip()


def normalize_ticket(value: object) -> str | None:
    text = normalize_text(value).upper()
    return text or None


def normalize_bool_text(value: object) -> str:
    return normalize_text(value).lower()


def normalize_grade(value: object) -> str | None:
    text = normalize_text(value).upper()
    return text or None


def write_output(path: str | None, content: str) -> None:
    if not path:
        return
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def infer_search_roots(ticket_path: Path, explicit_roots: list[str]) -> list[Path]:
    if explicit_roots:
        return [Path(raw).expanduser().resolve() for raw in explicit_roots]

    candidates = [ticket_path.parent.parent / "snapshots"]
    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots


def infer_ticket_scope(ticket_path: Path, ticket_frontmatter: dict) -> str:
    title = normalize_text(ticket_frontmatter.get("title")).lower()
    body = ticket_path.read_text(encoding="utf-8").lower()
    if "project-scope" in title or "master contract" in title or "project #" in title:
        return "project"
    if "phase-scoped" in body or re.search(r"\bphase\s+\d+\b", title) or re.search(r"\bphase\s+\d+\b", body):
        return "phase"
    if "task_type: creative_brief" in body and ("project-scope" in body or "master contract" in body):
        return "project"
    if normalize_text(ticket_frontmatter.get("phase")) and "creative brief" in title:
        return "phase"
    return "ticket"


def timestamp_for_record(record: BriefRecord) -> datetime | None:
    return parse_timestamp(record.updated) or parse_timestamp(record.captured)


def max_timestamp(*values: datetime | None) -> datetime | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return max(present)


def ticket_completion_anchor(ticket_frontmatter: dict) -> datetime | None:
    """
    Return the semantic ticket-freshness anchor for review gating.

    A closed creative-brief ticket can receive later mechanical `updated:` bumps
    from runtime close writes, dependency-guard notes, or evidence bookkeeping.
    Those touches should not make an otherwise fresh review stale when the
    delivered brief content did not change. Prefer `completed:` as the semantic
    close timestamp and fall back to `updated:` only when completion is absent.
    """

    return (
        parse_timestamp(ticket_frontmatter.get("completed"))
        or parse_timestamp(ticket_frontmatter.get("updated"))
        or parse_timestamp(ticket_frontmatter.get("created"))
    )


def select_target_brief(
    *,
    scanned_briefs: list[BriefRecord],
    ticket_path: Path,
    ticket_frontmatter: dict,
    ticket_id: str,
    project: str,
    phase: int | None,
    ticket_updated: datetime | None,
) -> tuple[BriefRecord | None, str]:
    explicit_scope = infer_ticket_scope(ticket_path, ticket_frontmatter)
    cutoff = datetime.max if ticket_updated is None else ticket_updated

    eligible = [
        record
        for record in scanned_briefs
        if record.project == project and (timestamp_for_record(record) or datetime.min) <= cutoff
    ]
    ticket_candidates = [record for record in eligible if matches_ticket(record, ticket_id)]
    phase_candidates = [record for record in eligible if matches_phase(record, phase)]
    project_candidates = [record for record in eligible if record.scope == "project"]

    if ticket_candidates:
        return sorted(ticket_candidates, key=brief_sort_key, reverse=True)[0], "ticket-specific brief matched this ticket"
    if explicit_scope == "project" and project_candidates:
        return sorted(project_candidates, key=brief_sort_key, reverse=True)[0], "project-scope ticket matched project brief"
    if phase_candidates:
        return sorted(phase_candidates, key=brief_sort_key, reverse=True)[0], "phase-scoped ticket matched phase brief"
    if project_candidates:
        return sorted(project_candidates, key=brief_sort_key, reverse=True)[0], "fell back to latest project brief"
    return None, "no applicable creative brief snapshot found"


def is_brief_review(path: Path, frontmatter: dict) -> bool:
    subtype = normalize_text(frontmatter.get("subtype")).lower()
    title = normalize_text(frontmatter.get("title")).lower()
    return subtype == "brief-review" or "brief review" in title or "brief-review" in path.name.lower()


def review_matches_target(path: Path, frontmatter: dict, target_brief: BriefRecord, ticket_id: str) -> bool:
    if normalize_text(frontmatter.get("project")) != target_brief.project:
        return False

    review_target = normalize_text(frontmatter.get("review_target"))
    if review_target:
        target_brief_filename = Path(target_brief.path).name.lower()
        review_target_filename = Path(review_target).name.lower()
        return review_target_filename == target_brief_filename

    review_phase_raw = normalize_text(frontmatter.get("phase"))
    review_phase = int(review_phase_raw) if review_phase_raw.isdigit() else None
    body = path.read_text(encoding="utf-8").lower()
    brief_filename = Path(target_brief.path).name.lower()
    ticket_token = ticket_id.lower()
    explicit_ticket = normalize_ticket(frontmatter.get("ticket"))

    if target_brief.scope == "phase":
        return review_phase == target_brief.phase or brief_filename in body
    if target_brief.scope == "ticket":
        return explicit_ticket == ticket_id or brief_filename in body or ticket_token in body
    # Project-scope: match only reviews with no phase/ticket (generic project reviews)
    # or reviews that explicitly name the project brief filename AND have no phase set.
    if review_phase is not None or explicit_ticket is not None:
        return False
    return True


def review_passes(frontmatter: dict, required_grade: str) -> tuple[bool, str]:
    advance_allowed = normalize_bool_text(frontmatter.get("advance_allowed"))
    if advance_allowed in {"yes", "true"}:
        return True, "advance_allowed=yes"

    actual_grade = normalize_grade(frontmatter.get("grade"))
    required_rank = GRADE_RANK.get(required_grade, GRADE_RANK["A"])
    actual_rank = GRADE_RANK.get(actual_grade or "", -1)
    if actual_rank >= required_rank:
        return True, f"grade {actual_grade} meets threshold {required_grade}"
    if actual_grade:
        return False, f"grade {actual_grade} below threshold {required_grade}"
    return False, f"missing passing signal (advance_allowed/grade) for threshold {required_grade}"


def serialize_record(record: BriefRecord | None) -> dict | None:
    if record is None:
        return None
    return {
        "path": record.path,
        "scope": record.scope,
        "title": record.title,
        "project": record.project,
        "phase": record.phase,
        "ticket": record.ticket,
        "captured": record.captured,
        "updated": record.updated,
    }


def load_body(path: Path) -> str:
    """Load markdown body without frontmatter."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].lstrip("\n")


def normalize_visual_target_mode(*values: object) -> str:
    """Normalize a visual quality target mode from candidate values."""
    for value in values:
        text = normalize_text(value).lower().replace("-", "_").replace(" ", "_")
        if text:
            return text
    return "none"


def run_brief_adequacy(brief_path: Path) -> dict[str, Any]:
    """Run the autonomous brief adequacy check in-process."""
    import check_brief_specificity_adequacy as adequacy

    return adequacy.evaluate_brief(brief_path)


def run_visual_ambition(brief_path: Path) -> dict[str, Any]:
    """Detect visual ambition signals for a brief."""
    import detect_visual_ambition

    return detect_visual_ambition.detect_ambition(brief_path)


def resolve_visual_spec_planning(
    *,
    ticket_path: Path,
    ticket_frontmatter: dict[str, Any],
    brief_path: Path,
    brief_frontmatter: dict[str, Any],
    project: str,
) -> dict[str, Any]:
    """Determine whether a downstream visual-spec ticket/plan marker exists."""
    if str(brief_frontmatter.get("spawns_visual_spec") or "").strip():
        brief_declares = normalize_bool_text(brief_frontmatter.get("spawns_visual_spec")) in {"true", "yes"}
        if brief_declares:
            return {"planned": True, "reason": "brief frontmatter declares spawns_visual_spec=true", "matches": [str(brief_path)]}
    if normalize_bool_text(ticket_frontmatter.get("spawns_visual_spec")) in {"true", "yes"}:
        return {"planned": True, "reason": "ticket frontmatter declares spawns_visual_spec=true", "matches": [str(ticket_path)]}

    matches: list[str] = []
    if ticket_path.parent.exists():
        for candidate in sorted(ticket_path.parent.glob("*.md")):
            if candidate.resolve() == ticket_path.resolve():
                continue
            frontmatter = parse_frontmatter_map(candidate)
            if normalize_text(frontmatter.get("project")) != project:
                continue
            task_type = normalize_text(frontmatter.get("task_type")).lower()
            title = normalize_text(frontmatter.get("title")).lower()
            if task_type == "visual_spec" or "visual spec" in title or "visual-spec" in candidate.name.lower():
                matches.append(str(candidate.resolve()))
    return {
        "planned": bool(matches),
        "reason": "found downstream visual-spec ticket(s)" if matches else "no downstream visual-spec ticket or spawns_visual_spec marker found",
        "matches": matches,
    }


def detect_pixel_token_overreach(brief_body: str) -> dict[str, Any]:
    """Detect token-level literals that belong in a visual spec rather than the brief."""
    occurrences = HEX_LITERAL_RE.findall(brief_body) + PIXEL_LITERAL_RE.findall(brief_body)
    deduped: list[str] = []
    seen: set[str] = set()
    for occurrence in occurrences:
        key = occurrence.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(occurrence)
    return {
        "found": bool(deduped),
        "occurrences": deduped[:20],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-path", required=True, help="Path to the creative-brief ticket.")
    parser.add_argument("--required-grade", default="A", help="Minimum passing grade when advance_allowed is absent.")
    parser.add_argument("--search-root", action="append", default=[], help="Optional snapshot root to scan. May be repeated.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    parser.add_argument("--markdown-out", help="Optional markdown output path.")
    return parser.parse_args()


def build_report(args: argparse.Namespace) -> dict:
    ticket_path = Path(args.ticket_path).expanduser().resolve()
    ticket_frontmatter = parse_frontmatter_map(ticket_path)
    ticket_id = normalize_ticket(ticket_frontmatter.get("id")) or ticket_path.stem.upper()
    project = normalize_text(ticket_frontmatter.get("project"))
    phase_text = normalize_text(ticket_frontmatter.get("phase"))
    phase = int(phase_text) if phase_text.isdigit() else None
    ticket_status = normalize_text(ticket_frontmatter.get("status")).lower()
    ticket_updated = parse_timestamp(ticket_frontmatter.get("updated"))
    ticket_completed_anchor = ticket_completion_anchor(ticket_frontmatter)
    search_roots = infer_search_roots(ticket_path, args.search_root)
    scanned_briefs = scan_briefs(search_roots, project) if project else []
    target_brief, selection_reason = select_target_brief(
        scanned_briefs=scanned_briefs,
        ticket_path=ticket_path,
        ticket_frontmatter=ticket_frontmatter,
        ticket_id=ticket_id,
        project=project,
        phase=phase,
        ticket_updated=ticket_updated,
    )
    target_brief_updated = timestamp_for_record(target_brief) if target_brief is not None else None
    freshness_anchor = max_timestamp(target_brief_updated, ticket_completed_anchor)

    review_matches: list[dict] = []
    latest_review: dict | None = None
    latest_review_frontmatter: dict | None = None
    latest_review_ts: datetime | None = None
    if target_brief is not None:
        for root in search_roots:
            if not root.exists():
                continue
            for path in root.rglob("*.md"):
                frontmatter = parse_frontmatter_map(path)
                if not is_brief_review(path, frontmatter):
                    continue
                if not review_matches_target(path, frontmatter, target_brief, ticket_id):
                    continue
                review_ts = (
                    parse_timestamp(frontmatter.get("updated"))
                    or parse_timestamp(frontmatter.get("captured"))
                    or parse_timestamp(frontmatter.get("created"))
                )
                entry = {
                    "path": str(path.resolve()),
                    "grade": normalize_grade(frontmatter.get("grade")),
                    "advance_allowed": normalize_bool_text(frontmatter.get("advance_allowed")),
                    "advance_threshold": normalize_grade(frontmatter.get("advance_threshold")),
                    "phase": frontmatter.get("phase"),
                    "updated": review_ts.isoformat(timespec="seconds") if review_ts else None,
                }
                review_matches.append(entry)
                if latest_review_ts is None or (review_ts or datetime.min) >= latest_review_ts:
                    latest_review = entry
                    latest_review_frontmatter = frontmatter
                    latest_review_ts = review_ts or datetime.min

    # The matching brief review must not predate the delivered brief content or
    # the semantic ticket completion anchor. We intentionally do not key this to
    # every later ticket `updated:` bump: post-close work-log/guard bookkeeping is
    # not a content change and should not force another review loop.
    review_is_fresh = bool(
        latest_review_ts and freshness_anchor
        and latest_review_ts >= freshness_anchor
    )
    review_passed, pass_reason = review_passes(latest_review_frontmatter or {}, normalize_grade(args.required_grade) or "A")
    if latest_review_frontmatter is None:
        review_passed = False
        pass_reason = "no matching brief-review snapshot found"

    checks = [
        {
            "name": "creative_brief_ticket_closed",
            "ok": ticket_status in {"closed", "done"},
            "details": f"Ticket status is `{ticket_status or 'missing'}`.",
        },
        {
            "name": "target_brief_found",
            "ok": target_brief is not None,
            "details": selection_reason,
        },
        {
            "name": "matching_review_found",
            "ok": latest_review is not None,
            "details": f"{len(review_matches)} matching brief review(s) found." if latest_review else "No matching brief review snapshots found.",
        },
        {
            "name": "review_fresh",
            "ok": review_is_fresh,
            "details": (
                f"Latest review timestamp {latest_review.get('updated')} is fresh relative to freshness anchor {freshness_anchor.isoformat(timespec='seconds')}."
                if review_is_fresh and latest_review and freshness_anchor
                else (
                    f"Latest review timestamp {latest_review.get('updated')} does not postdate freshness anchor {freshness_anchor.isoformat(timespec='seconds')}."
                    if latest_review and freshness_anchor
                    else "Missing ticket/review timestamp for freshness check."
                )
            ),
        },
        {
            "name": "review_passes_threshold",
            "ok": review_passed,
            "details": pass_reason,
        },
    ]

    target_brief_path = Path(target_brief.path).expanduser().resolve() if target_brief is not None else None
    target_brief_frontmatter = parse_frontmatter_map(target_brief_path) if target_brief_path and target_brief_path.exists() else {}
    target_brief_body = load_body(target_brief_path) if target_brief_path and target_brief_path.exists() else ""
    visual_quality_target_mode = normalize_visual_target_mode(
        target_brief_frontmatter.get("visual_quality_target_mode"),
        ticket_frontmatter.get("visual_quality_target_mode"),
    )

    ambition_report: dict[str, Any] | None = None
    adequacy_report: dict[str, Any] | None = None
    vs_plan_report: dict[str, Any] | None = None
    pixel_token_report: dict[str, Any] | None = None

    if target_brief_path and target_brief_path.exists():
        ambition_report = run_visual_ambition(target_brief_path)
        adequacy_report = run_brief_adequacy(target_brief_path)
        pixel_token_report = detect_pixel_token_overreach(target_brief_body)
        vs_plan_report = resolve_visual_spec_planning(
            ticket_path=ticket_path,
            ticket_frontmatter=ticket_frontmatter,
            brief_path=target_brief_path,
            brief_frontmatter=target_brief_frontmatter,
            project=project,
        )

        ambition_detected = bool(ambition_report.get("ambition_detected")) if ambition_report else False
        require_vs_plan = ambition_detected and visual_quality_target_mode != "none"
        adequacy_verdict = normalize_text((adequacy_report or {}).get("verdict")).lower()
        adequacy_ok = adequacy_verdict in {"pass", "pass_with_low_confidence_flag"}
        adequacy_details: dict[str, Any] | str = adequacy_report or "brief adequacy did not run"
        if adequacy_verdict == "pass_with_low_confidence_flag" and isinstance(adequacy_details, dict):
            adequacy_details = {**adequacy_details, "low_confidence": True}

        checks.extend(
            [
                {
                    "name": "visual_ambition_detected",
                    "ok": True,
                    "details": ambition_report or {"ambition_detected": False, "ambition_score": "none"},
                },
                {
                    "name": "brief_specificity_adequacy",
                    "ok": adequacy_ok,
                    "details": adequacy_details,
                },
                {
                    "name": "visual_spec_handoff_planned",
                    "ok": (not require_vs_plan) or bool(vs_plan_report and vs_plan_report.get("planned")),
                    "details": {
                        "required": require_vs_plan,
                        "visual_quality_target_mode": visual_quality_target_mode,
                        "ambition_detected": ambition_detected,
                        "planning": vs_plan_report or {"planned": False, "reason": "target brief unavailable"},
                    },
                },
                {
                    "name": "brief_avoids_visual_spec_token_literals",
                    "ok": True,
                    "details": {
                        "warning": bool(pixel_token_report and pixel_token_report.get("found")),
                        "message": (
                            "Brief contains pixel/token literals that should usually live in the visual spec."
                            if pixel_token_report and pixel_token_report.get("found")
                            else "No obvious hex/pixel literals found in the brief body."
                        ),
                        "occurrences": (pixel_token_report or {}).get("occurrences", []),
                    },
                },
            ]
        )

    verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"
    return {
        "generated_at": now(),
        "ticket_path": str(ticket_path),
        "ticket_id": ticket_id,
        "project": project,
        "phase": phase,
        "ticket_status": ticket_status,
        "ticket_updated": ticket_updated.isoformat(timespec="seconds") if ticket_updated else None,
        "ticket_completion_anchor": ticket_completed_anchor.isoformat(timespec="seconds") if ticket_completed_anchor else None,
        "target_brief_updated": target_brief_updated.isoformat(timespec="seconds") if target_brief_updated else None,
        "freshness_anchor": freshness_anchor.isoformat(timespec="seconds") if freshness_anchor else None,
        "required_grade": normalize_grade(args.required_grade) or "A",
        "search_roots": [str(path) for path in search_roots],
        "selection_reason": selection_reason,
        "visual_quality_target_mode": visual_quality_target_mode,
        "target_brief": serialize_record(target_brief),
        "matching_reviews": sorted(review_matches, key=lambda entry: entry.get("updated") or "", reverse=True),
        "latest_review": latest_review,
        "visual_ambition": ambition_report,
        "brief_specificity_adequacy": adequacy_report,
        "visual_spec_planning": vs_plan_report,
        "brief_visual_spec_token_warning": pixel_token_report,
        "checks": checks,
        "verdict": verdict,
    }


def render_markdown(report: dict) -> str:
    lines = [
        f"# Brief Gate Check — {report['ticket_id']}",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Project: {report['project'] or 'N/A'}",
        f"- Phase: {report['phase'] if report['phase'] is not None else 'N/A'}",
        f"- Required grade: {report['required_grade']}",
        f"- Verdict: {report['verdict']}",
        "",
    ]
    target_brief = report.get("target_brief")
    lines.extend(["## Target Brief", ""])
    if target_brief:
        lines.append(f"- `{target_brief['scope']}` — `{target_brief['title']}`")
        lines.append(f"- Path: `{target_brief['path']}`")
        lines.append(f"- Selection: {report['selection_reason']}")
    else:
        lines.append(f"- Missing target brief. {report['selection_reason']}")

    lines.extend(["", "## Checks", ""])
    for check in report["checks"]:
        icon = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- **{icon}** `{check['name']}` — {check['details']}")

    lines.extend(["", "## Matching Reviews", ""])
    reviews = report.get("matching_reviews") or []
    if not reviews:
        lines.append("- None")
    else:
        for review in reviews:
            lines.append(
                f"- `{review['path']}` — grade `{review.get('grade') or 'N/A'}`, advance_allowed `{review.get('advance_allowed') or 'N/A'}`, updated `{review.get('updated') or 'N/A'}`"
            )
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(args)
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown_text = render_markdown(report)
    write_output(args.json_out, json_text)
    write_output(args.markdown_out, markdown_text)
    if not args.json_out and not args.markdown_out:
        sys.stdout.write(json_text)
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
