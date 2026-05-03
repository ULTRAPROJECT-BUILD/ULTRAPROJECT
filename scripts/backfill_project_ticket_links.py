#!/usr/bin/env python3
"""
Backfill missing project task-list links for tickets already in the vault.

This is a repair tool for legacy projects created before create-ticket became
the sole project-task writer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ensure_project_ticket_link import ensure_ticket_link, parse_frontmatter_map


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    parser.add_argument("--write", action="store_true", help="Apply changes in place. Default is dry-run.")
    parser.add_argument("--project-path", help="Optional project markdown path to limit the scan.")
    parser.add_argument("--json-out", help="Optional path for the JSON report.")
    return parser.parse_args()


def iter_project_paths(root: Path, project_path: str | None) -> list[Path]:
    if project_path:
        return [Path(project_path).expanduser().resolve()]

    paths = list((root / "vault" / "projects").glob("*.md"))
    paths.extend((root / "vault" / "clients").glob("*" + "/projects/*.md"))
    return sorted(path.resolve() for path in paths)


def ticket_dir_for_project(project_path: Path) -> Path:
    return project_path.parent.parent / "tickets"


def tickets_for_project(project_path: Path) -> list[Path]:
    ticket_dir = ticket_dir_for_project(project_path)
    if not ticket_dir.exists():
        return []

    project_slug = project_path.stem
    matches: list[tuple[int, Path]] = []
    for ticket_path in ticket_dir.glob("T-*.md"):
        data = parse_frontmatter_map(ticket_path)
        if str(data.get("project", "")).strip() != project_slug:
            continue
        ticket_id = str(data.get("id", "")).strip()
        try:
            ticket_num = int(ticket_id.split("-", 1)[1])
        except (IndexError, ValueError):
            ticket_num = 999999
        matches.append((ticket_num, ticket_path.resolve()))
    return [path for _, path in sorted(matches)]


def build_report(root: Path, project_path: str | None, write: bool) -> dict:
    project_paths = iter_project_paths(root, project_path)
    results: list[dict] = []
    tickets_scanned = 0
    missing_links = 0

    for current_project_path in project_paths:
        for ticket_path in tickets_for_project(current_project_path):
            tickets_scanned += 1
            try:
                report = ensure_ticket_link(ticket_path, current_project_path, dry_run=not write)
            except Exception as exc:  # noqa: BLE001
                report = {
                    "ticket_path": str(ticket_path),
                    "project_path": str(current_project_path),
                    "ticket_id": "",
                    "ticket_title": "",
                    "canonical_line": "",
                    "changed": False,
                    "action": "error",
                    "error": str(exc),
                    "dry_run": not write,
                }
            if report["action"] != "already_linked":
                missing_links += 1
            results.append(report)

    changed_entries = [item for item in results if item["changed"]]
    changed_projects = sorted({item["project_path"] for item in changed_entries})
    errors = sum(1 for item in results if item["action"] == "error")
    return {
        "root": str(root),
        "write": write,
        "projects_scanned": len(project_paths),
        "tickets_scanned": tickets_scanned,
        "missing_links_found": missing_links,
        "errors": errors,
        "projects_with_missing_links": len(changed_projects),
        "project_files_changed": len(changed_projects) if write else 0,
        "project_files_that_would_change": len(changed_projects) if not write else 0,
        "ticket_links_changed": len(changed_entries) if write else 0,
        "ticket_links_that_would_change": len(changed_entries) if not write else 0,
        "results": results,
    }


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    report = build_report(root, args.project_path, args.write)
    payload = json.dumps(report, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
