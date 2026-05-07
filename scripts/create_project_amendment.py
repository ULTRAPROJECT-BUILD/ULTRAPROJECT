#!/usr/bin/env python3
"""
Create a structured mid-project amendment artifact for change control.

This writes a snapshot under the project's snapshots directory and updates the
project file's `## Pending Amendments` section so the orchestrator can see the
change without rediscovering it from raw email text.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_project_context import (
    collect_tickets,
    discover_project_layout,
    find_latest_project_plan,
    parse_phase_block,
    phase_display_number,
    parse_frontmatter_map,
    read_project_body,
    relative_to_platform,
)

PIVOT_PATTERNS = (
    "stop this",
    "stop working on",
    "pause this project",
    "pivot to",
    "instead build",
    "instead do",
    "replace this with",
    "scrap this",
    "kill this",
    "abandon this",
    "new direction",
)

REPLAN_PATTERNS = (
    "change the architecture",
    "re-architect",
    "rearchitecture",
    "new workstream",
    "new product",
    "browser extension",
    "mobile app",
    "desktop app",
    "service account",
    "multi-tenant",
    "multi tenant",
    "multi workspace",
    "add a new phase",
    "phase 2",
    "phase 3",
    "support multiple repos",
    "support multiple projects",
    "separate project",
)

PHASE_PATTERNS = (
    "also add",
    "also include",
    "need support for",
    "must support",
    "add support for",
    "new screen",
    "new surface",
    "new workflow",
    "new view",
    "new page",
    "new endpoint",
    "upload",
    "export",
    "import",
    "integration",
)

MINOR_PATTERNS = (
    "fix",
    "tweak",
    "polish",
    "rename",
    "copy",
    "wording",
    "spacing",
    "label",
    "button",
    "icon",
    "small",
    "minor",
)

STATUS_CLOSED = {"applied", "resolved", "superseded", "closed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", required=True, help="Path to the project markdown file.")
    parser.add_argument("--request-text", required=True, help="The new requested change text.")
    parser.add_argument("--source-kind", default="email", help="Source of the request (email, admin, note).")
    parser.add_argument("--source-subject", default="", help="Optional source subject/summary.")
    parser.add_argument("--source-message-id", default="", help="Optional message id or source reference.")
    parser.add_argument(
        "--classification",
        choices=("minor_ticket_delta", "phase_amendment", "project_replan", "pivot"),
        help="Optional explicit override for the classification.",
    )
    parser.add_argument("--captured-at", help="Optional explicit timestamp in local wall-clock format.")
    parser.add_argument("--status", default="pending", help="Initial amendment status.")
    parser.add_argument("--out", help="Optional explicit output path for the amendment snapshot.")
    parser.add_argument(
        "--skip-project-update",
        action="store_true",
        help="Do not update the project markdown Pending Amendments section.",
    )
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S %Z %z")


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return cleaned[:64] or "change-request"


def summarize_request(text: str) -> str:
    compact = " ".join(text.split())
    if len(compact) <= 140:
        return compact
    return compact[:137].rstrip() + "..."


def classify_request(text: str) -> tuple[str, str]:
    lowered = " ".join(text.lower().split())
    if any(token in lowered for token in PIVOT_PATTERNS):
        return (
            "pivot",
            "The request changes the project's direction enough that continuing the current plan would be misleading.",
        )
    if any(token in lowered for token in REPLAN_PATTERNS):
        return (
            "project_replan",
            "The request changes architecture, scope shape, or workstreams enough that the project plan should be rebased before more execution.",
        )
    if any(token in lowered for token in PHASE_PATTERNS):
        return (
            "phase_amendment",
            "The request adds or changes meaningful work inside the active project, but still fits the current project mission.",
        )
    if any(token in lowered for token in MINOR_PATTERNS):
        return (
            "minor_ticket_delta",
            "The request looks like a bounded tweak or follow-up that can be handled with scoped ticket changes without replanning the mission.",
        )
    return (
        "phase_amendment",
        "Defaulting to a phase amendment because the request changes in-flight work but does not clearly require a full pivot.",
    )


def apply_mode_for(classification: str) -> str:
    return {
        "minor_ticket_delta": "direct_ticket_delta",
        "phase_amendment": "phase_brief_delta",
        "project_replan": "project_rebaseline",
        "pivot": "pivot_replace",
    }[classification]


def recommended_actions_for(classification: str) -> list[str]:
    if classification == "minor_ticket_delta":
        return [
            "Create one or more scoped follow-up tickets on the active project and link this amendment artifact in the ticket context.",
            "Keep the current project plan and phase map intact unless the proof contract or acceptance criteria change materially.",
            "Refresh current-context and artifact-index after the new tickets are added so downstream agents see the amended scope.",
        ]
    if classification == "phase_amendment":
        return [
            "Update or supplement the active phase brief before executing the new work so acceptance criteria and proof obligations stay honest.",
            "Create amendment execution ticket(s) that link back to this artifact and re-check whether downstream review/polish tickets should stay blocked until the amendment lands.",
            "Refresh current-context, artifact-index, and any visual/media indexes after the amendment tickets or brief delta are created.",
        ]
    if classification == "project_replan":
        return [
            "Pause further scope expansion until the project plan is rebased against this change request.",
            "Create a replan/rebaseline ticket or run the planning flow again so the project plan, quality contract, and phase map are updated together.",
            "Re-block downstream tickets that assume the old scope until the replan is accepted and reflected in the project artifacts.",
        ]
    return [
        "Pause the current project cleanly and record the pivot explicitly in the project file.",
        "Create a replacement project or successor scope for the new direction before resuming execution.",
        "Mark the old project's pivot/amendment chain resolved only after the replacement project shell exists.",
    ]


def impact_flags_for(classification: str) -> dict[str, bool]:
    if classification == "minor_ticket_delta":
        return {
            "requires_phase_brief_update": False,
            "requires_project_replan": False,
            "requires_ticket_reblock": False,
            "pause_current_execution": False,
        }
    if classification == "phase_amendment":
        return {
            "requires_phase_brief_update": True,
            "requires_project_replan": False,
            "requires_ticket_reblock": True,
            "pause_current_execution": False,
        }
    if classification == "project_replan":
        return {
            "requires_phase_brief_update": True,
            "requires_project_replan": True,
            "requires_ticket_reblock": True,
            "pause_current_execution": True,
        }
    return {
        "requires_phase_brief_update": False,
        "requires_project_replan": True,
        "requires_ticket_reblock": True,
        "pause_current_execution": True,
    }


def current_phase_summary(project_file: Path, layout: dict[str, Any]) -> dict[str, Any]:
    plan_path = find_latest_project_plan(layout, None)
    if not plan_path or not plan_path.exists():
        return {"number": None, "display": None, "title": "", "plan_path": None}
    plan_data = parse_frontmatter_map(plan_path)
    current_phase = plan_data.get("current_phase")
    total_phases = plan_data.get("total_phases")
    try:
        current_phase_int = int(current_phase)
    except (TypeError, ValueError):
        current_phase_int = None
    phase_block = parse_phase_block(plan_path, current_phase_int)
    return {
        "number": current_phase_int,
        "display": phase_display_number(current_phase_int, total_phases),
        "title": phase_block["title"] if phase_block else "",
        "plan_path": plan_path,
    }


def default_output_path(layout: dict[str, Any], project: str, request_text: str, captured_at: str) -> Path:
    stamp = captured_at.split("T", 1)[0]
    slug = slugify(request_text)[:48]
    return Path(layout["snapshots_dir"]) / f"{stamp}-project-amendment-{project}-{slug}.md"


def amendment_title(project_title: str) -> str:
    return f"Project Amendment — {project_title}"


def update_project_pending_amendments(
    project_file: Path,
    *,
    captured_at: str,
    relative_artifact_path: str,
    classification: str,
    status: str,
    summary: str,
) -> None:
    text = project_file.read_text(encoding="utf-8")
    marker = "## Pending Amendments"
    entry = f"- {captured_at}: `{relative_artifact_path}` — {classification} [{status}] — {summary}"
    if marker not in text:
        suffix = "" if text.endswith("\n") else "\n"
        text = f"{text}{suffix}\n{marker}\n\n{entry}\n"
        project_file.write_text(text, encoding="utf-8")
        return

    before, after = text.split(marker, 1)
    section_body = after.lstrip("\n")
    next_heading = re.search(r"^##\s+.+$", section_body, flags=re.MULTILINE)
    section = section_body[: next_heading.start()] if next_heading else section_body
    remainder = section_body[next_heading.start() :] if next_heading else ""
    lines = [line for line in section.strip("\n").splitlines() if line.strip()]
    if entry not in lines:
        lines.append(entry)
    new_section = marker + "\n\n" + "\n".join(lines) + "\n"
    project_file.write_text(before.rstrip() + "\n\n" + new_section + remainder, encoding="utf-8")


def build_markdown(payload: dict[str, Any]) -> str:
    fm = {
        "type": "snapshot",
        "subtype": "project-amendment",
        "title": payload["title"],
        "project": payload["project"],
        "client": payload["client"],
        "captured": payload["captured"],
        "updated": payload["captured"],
        "status": payload["status"],
        "classification": payload["classification"],
        "apply_mode": payload["apply_mode"],
        "source_kind": payload["source_kind"],
        "source_subject": payload["source_subject"],
        "source_message_id": payload["source_message_id"],
        "current_phase": payload["current_phase"],
        "current_phase_display": payload["current_phase_display"],
        "requires_phase_brief_update": payload["impact_flags"]["requires_phase_brief_update"],
        "requires_project_replan": payload["impact_flags"]["requires_project_replan"],
        "requires_ticket_reblock": payload["impact_flags"]["requires_ticket_reblock"],
        "pause_current_execution": payload["impact_flags"]["pause_current_execution"],
        "request_summary": payload["request_summary"],
    }
    lines = ["---", yaml.safe_dump(fm, sort_keys=False, allow_unicode=False).strip(), "---", ""]
    lines.extend(
        [
            f"# {payload['title']}",
            "",
            "## Request",
            "",
            payload["request_text"],
            "",
            "## Classification",
            "",
            f"- Class: `{payload['classification']}`",
            f"- Apply mode: `{payload['apply_mode']}`",
            f"- Reasoning: {payload['classification_reason']}",
            "",
            "## Current Project Context",
            "",
            f"- Project status: `{payload['project_status'] or 'unknown'}`",
            f"- Current phase: {payload['current_phase_label']}",
            f"- Active tickets now: {payload['active_ticket_count']}",
            "",
            "## Recommended Actions",
            "",
        ]
    )
    for action in payload["recommended_actions"]:
        lines.append(f"- {action}")
    lines.extend(
        [
            "",
            "## Source",
            "",
            f"- Source kind: `{payload['source_kind']}`",
        ]
    )
    if payload["source_subject"]:
        lines.append(f"- Source subject: {payload['source_subject']}")
    if payload["source_message_id"]:
        lines.append(f"- Source reference: `{payload['source_message_id']}`")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    project_file = Path(args.project_file).expanduser().resolve()
    layout = discover_project_layout(project_file)
    project_frontmatter, _project_body = read_project_body(project_file)
    project = layout["project"]
    captured_at = args.captured_at or now()
    if args.classification:
        classification = args.classification
        classification_reason = "Classification supplied explicitly."
    else:
        classification, classification_reason = classify_request(args.request_text)
    apply_mode = apply_mode_for(classification)
    impact_flags = impact_flags_for(classification)
    phase_info = current_phase_summary(project_file, layout)
    tickets = collect_tickets(layout, project)
    active_ticket_count = len([ticket for ticket in tickets if ticket.get("status") not in {"closed", ""}])
    current_phase_label = "No active phase recorded."
    if phase_info["number"] is not None:
        current_phase_label = f"Phase {phase_info['display']}"
        if phase_info["title"]:
            current_phase_label += f" — {phase_info['title']}"

    out_path = Path(args.out).expanduser().resolve() if args.out else default_output_path(layout, project, args.request_text, captured_at)
    payload = {
        "title": amendment_title(str(project_frontmatter.get("title", project)).strip().strip('"')),
        "project": project,
        "client": layout["client"],
        "captured": captured_at,
        "status": args.status,
        "classification": classification,
        "classification_reason": classification_reason,
        "apply_mode": apply_mode,
        "source_kind": args.source_kind,
        "source_subject": args.source_subject,
        "source_message_id": args.source_message_id,
        "current_phase": phase_info["number"],
        "current_phase_display": phase_info["display"],
        "current_phase_label": current_phase_label,
        "project_status": str(project_frontmatter.get("status", "")).strip(),
        "active_ticket_count": active_ticket_count,
        "request_summary": summarize_request(args.request_text),
        "request_text": args.request_text.strip(),
        "impact_flags": impact_flags,
        "recommended_actions": recommended_actions_for(classification),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_markdown(payload), encoding="utf-8")

    if not args.skip_project_update:
        update_project_pending_amendments(
            project_file,
            captured_at=captured_at,
            relative_artifact_path=relative_to_platform(out_path, Path(layout["platform_root"])),
            classification=classification,
            status=args.status,
            summary=payload["request_summary"],
        )

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
