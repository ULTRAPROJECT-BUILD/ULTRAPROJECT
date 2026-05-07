#!/usr/bin/env python3
"""
Ensure a ticket appears in its owning project's ## Tasks section.

This script is the canonical writer for project task-list entries. It creates
future links in a single format and can also be reused by backfill/repair jobs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TASKS_HEADING_RE = re.compile(r"^## Tasks\s*$", re.MULTILINE)
LEVEL2_HEADING_RE = re.compile(r"^##\s+", re.MULTILINE)
PLACEHOLDER_RE = re.compile(r"^\(Tickets will be .*?\)\s*$", re.MULTILINE)
DONE_STATUSES = {"closed", "done", "complete"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-path", required=True, help="Ticket markdown path.")
    parser.add_argument("--project-path", help="Optional explicit project markdown path.")
    parser.add_argument("--dry-run", action="store_true", help="Report the action without writing changes.")
    parser.add_argument("--json-out", help="Optional path for the JSON report.")
    return parser.parse_args()


def parse_scalar(raw_value: str) -> object:
    value = raw_value.strip()
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() in {"null", "~"}:
        return ""
    return value.strip("\"'")


def parse_frontmatter_map(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}

    data: dict[str, object] = {}
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    return data


def infer_ticket_id(ticket_path: Path, ticket_data: dict) -> str:
    explicit = str(ticket_data.get("id", "")).strip()
    if explicit:
        return explicit

    match = re.match(r"^(T-\d+)\b", ticket_path.stem)
    if match:
        return match.group(1)
    return ""


def infer_ticket_title(ticket_path: Path, ticket_data: dict) -> str:
    explicit = str(ticket_data.get("title", "")).strip()
    if explicit:
        return explicit

    text = ticket_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def resolve_project_path(ticket_path: Path, ticket_data: dict, explicit_project_path: str | None) -> Path:
    if explicit_project_path:
        return Path(explicit_project_path).expanduser().resolve()

    project_slug = str(ticket_data.get("project", "")).strip()
    if not project_slug:
        raise ValueError(f"{ticket_path} is missing `project` in frontmatter.")

    project_dir = ticket_path.resolve().parent.parent / "projects"
    return project_dir / f"{project_slug}.md"


def canonical_task_line(ticket_path: Path, ticket_data: dict) -> str:
    ticket_id = infer_ticket_id(ticket_path, ticket_data)
    title = infer_ticket_title(ticket_path, ticket_data)
    status = str(ticket_data.get("status", "")).strip().lower()
    if not ticket_id or not title:
        raise ValueError(f"{ticket_path} is missing a usable ticket ID or title.")

    checkbox = "x" if status in DONE_STATUSES else " "
    return f"- [{checkbox}] [[{ticket_path.stem}|{ticket_id}]]: {title}"


def task_entry_exists(tasks_body: str, ticket_path: Path, ticket_data: dict) -> bool:
    ticket_id = infer_ticket_id(ticket_path, ticket_data)
    ticket_stem = ticket_path.stem
    pattern = re.compile(
        rf"(\[\[{re.escape(ticket_stem)}(?:\|[^\]]+)?\]\]|\b{re.escape(ticket_id)}\b)"
    )
    return any(pattern.search(line) for line in tasks_body.splitlines())


def locate_tasks_section(text: str) -> tuple[int, int, int] | None:
    match = TASKS_HEADING_RE.search(text)
    if not match:
        return None
    body_start = match.end()
    next_heading = LEVEL2_HEADING_RE.search(text, body_start)
    section_end = next_heading.start() if next_heading else len(text)
    return match.start(), body_start, section_end


def ensure_ticket_link_content(project_text: str, ticket_path: Path, ticket_data: dict) -> tuple[str, bool, str, str]:
    line = canonical_task_line(ticket_path, ticket_data)
    tasks_section = locate_tasks_section(project_text)

    if tasks_section is None:
        notes_match = re.search(r"^## Notes\s*$", project_text, re.MULTILINE)
        insertion = f"## Tasks\n\n{line}\n\n"
        if notes_match:
            new_text = project_text[: notes_match.start()].rstrip("\n") + "\n\n" + insertion + project_text[notes_match.start() :]
        else:
            new_text = project_text.rstrip("\n") + "\n\n" + insertion
        return new_text, True, "created_tasks_section", line

    _, body_start, section_end = tasks_section
    tasks_body = project_text[body_start:section_end]
    placeholder_match = PLACEHOLDER_RE.search(tasks_body)

    if task_entry_exists(tasks_body, ticket_path, ticket_data):
        if placeholder_match:
            new_body = PLACEHOLDER_RE.sub("", tasks_body, count=1)
            new_body = re.sub(r"\n{3,}", "\n\n", new_body)
            new_text = project_text[:body_start] + new_body + project_text[section_end:]
            return new_text, True, "removed_tasks_placeholder", line
        return project_text, False, "already_linked", line

    if placeholder_match:
        new_body = PLACEHOLDER_RE.sub(line, tasks_body, count=1)
        new_text = project_text[:body_start] + new_body + project_text[section_end:]
        return new_text, True, "replaced_tasks_placeholder", line

    trimmed_body = tasks_body.rstrip("\n")
    if trimmed_body.strip():
        new_body = trimmed_body + "\n" + line + "\n"
    else:
        new_body = "\n\n" + line + "\n"

    new_text = project_text[:body_start] + new_body + project_text[section_end:]
    return new_text, True, "appended_task_link", line


def ensure_ticket_link(ticket_path: Path, project_path: Path | None = None, dry_run: bool = False) -> dict:
    ticket_path = ticket_path.expanduser().resolve()
    ticket_data = parse_frontmatter_map(ticket_path)
    project_path = resolve_project_path(ticket_path, ticket_data, str(project_path) if project_path else None)
    if not project_path.exists():
        raise FileNotFoundError(f"Project file not found: {project_path}")

    project_text = project_path.read_text(encoding="utf-8")
    new_text, changed, action, line = ensure_ticket_link_content(project_text, ticket_path, ticket_data)
    if changed and not dry_run:
        project_path.write_text(new_text, encoding="utf-8")

    return {
        "ticket_path": str(ticket_path),
        "ticket_id": infer_ticket_id(ticket_path, ticket_data),
        "ticket_title": infer_ticket_title(ticket_path, ticket_data),
        "project_path": str(project_path),
        "canonical_line": line,
        "changed": changed,
        "action": action,
        "dry_run": dry_run,
    }


def main() -> int:
    args = parse_args()
    try:
        report = ensure_ticket_link(
            Path(args.ticket_path),
            project_path=Path(args.project_path).expanduser().resolve() if args.project_path else None,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        report = {
            "ticket_path": args.ticket_path,
            "project_path": args.project_path or "",
            "changed": False,
            "action": "error",
            "error": str(exc),
            "dry_run": args.dry_run,
        }
        payload = json.dumps(report, indent=2)
        if args.json_out:
            Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
        print(payload)
        return 1

    payload = json.dumps(report, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
