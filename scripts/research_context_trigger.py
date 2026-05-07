#!/usr/bin/env python3
"""
Decide whether a project must run the research-context skill before planning.

The decision is deterministic and offline. It reads the project file, explicit
frontmatter overrides, goal/context text, tags, and the latest research snapshot
age, then writes machine-readable JSON plus a short markdown report.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any


CURRENTNESS_TERMS = [
    "latest",
    "current",
    "recent",
    "new",
    "launch",
    "launched",
    "vendor",
    "tool",
    "tools",
    "library",
    "libraries",
    "framework",
    "version",
    "versions",
    "deprecated",
    "breaking change",
    "best practice",
    "benchmark",
    "reference",
    "competitor",
    "genre",
    "api",
    "sdk",
    "mcp",
    "plugin",
    "github",
    "x",
    "twitter",
    "hacker news",
    "hn",
    "openai",
    "anthropic",
    "claude",
    "codex",
    "remotion",
]
RESEARCH_TAGS = {
    "creative",
    "brief",
    "video",
    "website",
    "landing-page",
    "frontend",
    "design",
    "app",
    "mcp",
    "api",
    "library",
    "tooling",
    "vendor",
    "market-research",
    "competitive",
    "launch",
    "content",
    "deck",
    "presentation",
    "marketing",
    "game",
    "ai",
    "software",
    "integration",
    "automation",
    "data",
}
LOCAL_ONLY_TAGS = {
    "bookkeeping",
    "archive",
    "cleanup",
    "status",
    "vault-maintenance",
    "data-deletion",
    "regression-only",
    "docs-local",
    "rename",
    "formatting",
}
STALE_AFTER_DAYS = 7


class FrontmatterError(ValueError):
    """Raised when markdown frontmatter is syntactically malformed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", required=True, help="Project markdown path.")
    parser.add_argument("--goal", required=True, help="Goal text from the operator or project frontmatter.")
    parser.add_argument("--json-out", required=True, help="Where to write the JSON decision report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the markdown decision report.")
    return parser.parse_args()


def normalize_label(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def parse_scalar(value: str) -> object:
    text = value.strip()
    if not text:
        return ""
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if text.startswith("["):
        if not text.endswith("]"):
            raise FrontmatterError(f"malformed inline list: {text}")
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",") if item.strip()]
    if text.count('"') % 2 or text.count("'") % 2:
        raise FrontmatterError(f"unbalanced quote in value: {text}")
    return text.strip("\"'")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    lines = text.splitlines()
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            frontmatter = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return frontmatter, body
    raise FrontmatterError("frontmatter opening marker has no closing marker")


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    frontmatter_text, body = split_frontmatter(text)
    data: dict[str, Any] = {}
    current_list_key: str | None = None
    for line_number, raw_line in enumerate(frontmatter_text.splitlines(), start=2):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - "):
            if current_list_key is None:
                raise FrontmatterError(f"list item without list key at line {line_number}")
            items = data.setdefault(current_list_key, [])
            if not isinstance(items, list):
                raise FrontmatterError(f"list key collision at line {line_number}")
            items.append(parse_scalar(raw_line[4:]))
            continue
        if raw_line.startswith((" ", "\t")):
            raise FrontmatterError(f"unsupported indented frontmatter at line {line_number}")
        if ":" not in raw_line:
            raise FrontmatterError(f"missing ':' in frontmatter line {line_number}")
        key, value = raw_line.split(":", 1)
        key = key.strip()
        if not key:
            raise FrontmatterError(f"empty frontmatter key at line {line_number}")
        value = value.strip()
        if value == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = parse_scalar(value)
            current_list_key = None
    return data, body


def normalize_tags(value: object) -> list[str]:
    if isinstance(value, list):
        raw_values = value
    else:
        text = str(value or "").strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        raw_values = re.split(r"[, ]+", text) if text else []
    tags = []
    seen = set()
    for item in raw_values:
        tag = normalize_label(item).strip("\"'")
        if tag and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def extract_goal_from_body(body: str) -> str:
    match = re.search(r"^##\s+Goal\s*\n(.+?)(?:\n##\s+|\Z)", body, re.IGNORECASE | re.DOTALL | re.MULTILINE)
    return match.group(1).strip() if match else ""


def extract_context_from_body(body: str) -> str:
    sections = []
    for heading in ("Context", "Notes"):
        match = re.search(
            rf"^##\s+{heading}\s*\n(.+?)(?:\n##\s+|\Z)",
            body,
            re.IGNORECASE | re.DOTALL | re.MULTILINE,
        )
        if match:
            sections.append(match.group(1).strip())
    return "\n\n".join(sections)


def match_terms(text: str) -> list[str]:
    haystack = normalize_label(text)
    matches = []
    for term in CURRENTNESS_TERMS:
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, haystack):
            matches.append(term)
    return matches


def parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip().strip("\"'")
    match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?|\d{4}-\d{2}-\d{2})", text)
    if not match:
        return None
    try:
        return datetime.fromisoformat(match.group(1))
    except ValueError:
        return None


def infer_snapshots_root(project_file: Path, project: str) -> Path:
    resolved = project_file.resolve()
    if resolved.parent.name == "projects":
        root = resolved.parent.parent
        return root / "snapshots" / project
    return resolved.parent / "snapshots" / project


def is_research_snapshot(path: Path, project: str) -> tuple[bool, datetime | None]:
    if any(token in path.name for token in ("budget", "trigger", "check", "working")):
        return False, None
    try:
        frontmatter, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
    except Exception:
        frontmatter = {}
    subtype = normalize_label(frontmatter.get("subtype"))
    if subtype and subtype != "research-context":
        return False, None
    if project and normalize_label(frontmatter.get("project")) not in {"", normalize_label(project)}:
        return False, None
    captured = parse_timestamp(frontmatter.get("captured"))
    return True, captured


def latest_research_snapshot(project_file: Path, project: str) -> tuple[str | None, str | None, bool]:
    snapshots_root = infer_snapshots_root(project_file, project)
    if not snapshots_root.exists():
        return None, None, False
    candidates: list[tuple[datetime, str, Path]] = []
    for path in snapshots_root.glob("*-research-context-*.md"):
        ok, captured = is_research_snapshot(path, project)
        if not ok:
            continue
        timestamp = captured or datetime.fromtimestamp(path.stat().st_mtime)
        candidates.append((timestamp, timestamp.isoformat(timespec="minutes"), path.resolve()))
    if not candidates:
        return None, None, False
    timestamp, captured_text, path = max(candidates, key=lambda item: (item[0], str(item[2])))
    age_days = (date.today() - timestamp.date()).days
    return str(path), captured_text, age_days > STALE_AFTER_DAYS


def write_text(path: str, content: str) -> None:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def base_report(project: str | None = None) -> dict[str, Any]:
    return {
        "project": project,
        "decision": "error",
        "reason": "",
        "matched_keywords": [],
        "matched_tags": [],
        "local_only": False,
        "latest_snapshot": None,
        "latest_snapshot_captured": None,
        "stale": False,
        "stale_after_days": STALE_AFTER_DAYS,
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Research Context Trigger",
            "",
            f"- **Project:** {report.get('project') or 'unknown'}",
            f"- **Decision:** {report['decision']}",
            f"- **Reason:** {report['reason']}",
            f"- **Matched keywords:** {', '.join(report['matched_keywords']) or 'none'}",
            f"- **Matched tags:** {', '.join(report['matched_tags']) or 'none'}",
            f"- **Local only:** {str(report['local_only']).lower()}",
            f"- **Latest snapshot:** {report.get('latest_snapshot') or 'none'}",
            f"- **Latest captured:** {report.get('latest_snapshot_captured') or 'none'}",
            f"- **Stale:** {str(report['stale']).lower()}",
            f"- **Stale after days:** {report['stale_after_days']}",
            "",
        ]
    )


def final_decision(
    decision: str,
    reason: str,
    *,
    project: str,
    matched_keywords: list[str],
    matched_tags: list[str],
    local_only: bool,
    latest_snapshot: str | None,
    latest_snapshot_captured: str | None,
    stale: bool,
) -> dict[str, Any]:
    if decision == "required" and stale:
        decision = "refresh_required"
        reason = "latest_snapshot_stale"
    return {
        "project": project,
        "decision": decision,
        "reason": reason,
        "matched_keywords": matched_keywords,
        "matched_tags": matched_tags,
        "local_only": local_only,
        "latest_snapshot": latest_snapshot,
        "latest_snapshot_captured": latest_snapshot_captured,
        "stale": stale,
        "stale_after_days": STALE_AFTER_DAYS,
    }


def decide(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    project_file = Path(args.project_file).expanduser()
    try:
        text = project_file.read_text(encoding="utf-8")
    except OSError as exc:
        report = base_report()
        report["reason"] = f"missing_or_unreadable_project_file: {exc}"
        return report, 1
    try:
        frontmatter, body = parse_frontmatter(text)
    except FrontmatterError as exc:
        project = project_file.stem
        report = base_report(project)
        report["reason"] = f"malformed_yaml_frontmatter: {exc}"
        return report, 1

    project = str(frontmatter.get("project") or frontmatter.get("slug") or project_file.stem).strip()
    goal_text = "\n\n".join(
        part
        for part in [
            args.goal.strip(),
            str(frontmatter.get("goal") or "").strip(),
            extract_goal_from_body(body),
        ]
        if part
    )
    context_text = "\n\n".join(
        part
        for part in [
            str(frontmatter.get("context") or "").strip(),
            str(frontmatter.get("notes") or "").strip(),
            extract_context_from_body(body),
        ]
        if part
    )
    tags = normalize_tags(frontmatter.get("tags"))
    latest_snapshot, latest_captured, stale = latest_research_snapshot(project_file, project)

    override = normalize_label(frontmatter.get("research_context"))
    matched_keywords = match_terms(goal_text + "\n\n" + context_text)
    matched_tags = [tag for tag in tags if tag in RESEARCH_TAGS]
    local_only = bool(tags) and all(tag in LOCAL_ONLY_TAGS for tag in tags)

    if override == "skip":
        return (
            final_decision(
                "skip",
                "operator_override_skip",
                project=project,
                matched_keywords=matched_keywords,
                matched_tags=matched_tags,
                local_only=local_only,
                latest_snapshot=latest_snapshot,
                latest_snapshot_captured=latest_captured,
                stale=stale,
            ),
            0,
        )
    if override == "required":
        return (
            final_decision(
                "required",
                "operator_override_required",
                project=project,
                matched_keywords=matched_keywords,
                matched_tags=matched_tags,
                local_only=local_only,
                latest_snapshot=latest_snapshot,
                latest_snapshot_captured=latest_captured,
                stale=stale,
            ),
            0,
        )
    if frontmatter.get("research_context_required") is True:
        return (
            final_decision(
                "required",
                "frontmatter_research_context_required",
                project=project,
                matched_keywords=matched_keywords,
                matched_tags=matched_tags,
                local_only=local_only,
                latest_snapshot=latest_snapshot,
                latest_snapshot_captured=latest_captured,
                stale=stale,
            ),
            0,
        )
    if not tags and not goal_text.strip():
        return (
            final_decision(
                "required",
                "missing_goal_and_tags_safe_default",
                project=project,
                matched_keywords=matched_keywords,
                matched_tags=matched_tags,
                local_only=False,
                latest_snapshot=latest_snapshot,
                latest_snapshot_captured=latest_captured,
                stale=stale,
            ),
            0,
        )
    if matched_keywords:
        return (
            final_decision(
                "required",
                f"keyword:{matched_keywords[0]}",
                project=project,
                matched_keywords=matched_keywords,
                matched_tags=matched_tags,
                local_only=local_only,
                latest_snapshot=latest_snapshot,
                latest_snapshot_captured=latest_captured,
                stale=stale,
            ),
            0,
        )
    if matched_tags:
        return (
            final_decision(
                "required",
                f"tag:{matched_tags[0]}",
                project=project,
                matched_keywords=matched_keywords,
                matched_tags=matched_tags,
                local_only=local_only,
                latest_snapshot=latest_snapshot,
                latest_snapshot_captured=latest_captured,
                stale=stale,
            ),
            0,
        )
    if local_only:
        return (
            final_decision(
                "skip",
                "local_only_tags",
                project=project,
                matched_keywords=matched_keywords,
                matched_tags=matched_tags,
                local_only=True,
                latest_snapshot=latest_snapshot,
                latest_snapshot_captured=latest_captured,
                stale=stale,
            ),
            0,
        )
    if tags:
        return (
            final_decision(
                "required",
                "creative-brief-default",
                project=project,
                matched_keywords=matched_keywords,
                matched_tags=matched_tags,
                local_only=False,
                latest_snapshot=latest_snapshot,
                latest_snapshot_captured=latest_captured,
                stale=stale,
            ),
            0,
        )
    return (
        final_decision(
            "optional",
            "no_currentness_signals",
            project=project,
            matched_keywords=matched_keywords,
            matched_tags=matched_tags,
            local_only=False,
            latest_snapshot=latest_snapshot,
            latest_snapshot_captured=latest_captured,
            stale=False,
        ),
        0,
    )


def main() -> int:
    args = parse_args()
    report, exit_code = decide(args)
    write_text(args.json_out, json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_text(args.markdown_out, render_markdown(report))
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
