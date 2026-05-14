#!/usr/bin/env python3
"""Detect or apply ticket invalidations caused by a visual-spec amendment."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
VS_SCHEMA = REPO_ROOT / "schemas" / "visual-spec-frontmatter.schema.json"

REVIEW_TASK_TYPES = {"self_review", "quality_check", "artifact_polish_review", "visual_review", "code_review"}
BUILD_TASK_TYPES = {"code_build", "creative_build", "build", "game_dev", "mcp_build", "skill_build"}


@dataclass(frozen=True)
class TicketRecord:
    """A ticket path plus parsed frontmatter and body."""

    path: Path
    frontmatter: dict[str, Any]
    body: str


@dataclass(frozen=True)
class VisualSpecRecord:
    """A visual specification path plus parsed frontmatter."""

    path: Path
    frontmatter: dict[str, Any]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Project slug.")
    parser.add_argument("--client", help="Client slug. Omit for platform/internal work.")
    parser.add_argument("--vs-path", required=True, help="Amended visual-spec markdown path.")
    parser.add_argument("--action", choices=["detect", "apply"], required=True, help="Detect or apply invalidations.")
    parser.add_argument("--json-out", help="Optional path to write JSON output.")
    parser.add_argument("--vault-root", help="Optional vault root override; useful for isolated tests.")
    return parser.parse_args()


def now_iso() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    """Split a markdown document into frontmatter text and body."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} does not start with YAML frontmatter")
    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise ValueError(f"{path} has no closing YAML frontmatter delimiter")
    return "".join(lines[1:closing_index]), "".join(lines[closing_index + 1 :])


def load_markdown(path: Path) -> tuple[dict[str, Any], str]:
    """Read frontmatter and body from a markdown file."""
    frontmatter_text, body = split_frontmatter(path.read_text(encoding="utf-8"), path)
    data = yaml.safe_load(frontmatter_text)
    return (data if isinstance(data, dict) else {}), body


def parse_datetime(value: Any, field_name: str) -> datetime:
    """Parse an ISO timestamp as an aware UTC datetime."""
    if isinstance(value, datetime):
        parsed = value
    elif value is None or str(value).strip() == "":
        raise ValueError(f"{field_name} is missing")
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_datetime_value(value: Any, field_name: str) -> str:
    """Normalize a YAML timestamp value to explicit UTC ISO text."""
    return parse_datetime(value, field_name).isoformat()


def optional_text(value: Any) -> str | None:
    """Normalize an optional scalar."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def normalize_list(value: Any) -> list[str]:
    """Normalize scalar/list frontmatter values to a string list."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [text]


def resolve_vault_root(raw: str | None = None, anchor: Path | None = None) -> Path:
    """Resolve the active vault root from an override, anchor, environment, or cwd."""
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw).expanduser())
    env_root = os.environ.get("ONESHOT_VAULT_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser())
    if anchor:
        resolved_anchor = anchor.expanduser().resolve()
        candidates.extend([resolved_anchor, *resolved_anchor.parents])
    candidates.extend([REPO_ROOT / "vault", Path.cwd(), *Path.cwd().parents])
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.name == "vault":
            return resolved
        if (resolved / "vault").is_dir():
            return (resolved / "vault").resolve()
    raise FileNotFoundError("Could not locate vault root")


def infer_client(vs_path: Path, vault_root: Path, explicit_client: str | None) -> str:
    """Infer client slug from a VS path when possible."""
    if explicit_client:
        return explicit_client
    try:
        rel = vs_path.resolve().relative_to(vault_root)
    except ValueError:
        return "platform"
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "clients":
        return parts[1]
    return "platform"


def validate_visual_spec(path: Path, vault_root: Path) -> None:
    """Validate visual-spec frontmatter through validate_schema.py."""
    env = {**os.environ, "ONESHOT_VAULT_ROOT": str(vault_root)}
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "validate_schema.py"),
            "--artifact",
            str(path),
            "--schema",
            str(VS_SCHEMA),
            "--artifact-type",
            "yaml-frontmatter",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    result.check_returncode()


def bump_generation(vault_root: Path) -> dict[str, Any]:
    """Bump resolver generation after applying an amendment invalidation."""
    env = {**os.environ, "ONESHOT_VAULT_ROOT": str(vault_root)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "lock_visual_spec.py"), "bump-generation"],
        capture_output=True,
        text=True,
        env=env,
    )
    result.check_returncode()
    return json.loads(result.stdout or "{}")


def visual_spec_roots(vault_root: Path, project: str, client: str) -> list[Path]:
    """Return candidate directories containing visual-spec snapshots."""
    roots: list[Path] = []
    if client != "platform":
        roots.append(vault_root / "clients" / client / "snapshots" / project)
    roots.append(vault_root / "snapshots" / project)
    return roots


def discover_visual_specs(vault_root: Path, project: str, client: str, amended_path: Path) -> list[VisualSpecRecord]:
    """Discover visual-spec revisions, including the amended path even if outside normal roots."""
    records: list[VisualSpecRecord] = []
    seen: set[Path] = set()
    candidate_paths = [amended_path.resolve()]
    for root in visual_spec_roots(vault_root, project, client):
        if root.exists():
            candidate_paths.extend(sorted(root.rglob("*-visual-spec-*.md")))
    for path in candidate_paths:
        resolved = path.resolve()
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        try:
            frontmatter, _ = load_markdown(resolved)
        except Exception:
            continue
        if frontmatter.get("project") != project:
            continue
        records.append(VisualSpecRecord(path=resolved, frontmatter=frontmatter))
    return records


def collect_superseded_revisions(amended: dict[str, Any], all_specs: list[VisualSpecRecord]) -> set[str]:
    """Collect all prior revision IDs in the amended VS supersedes chain."""
    by_revision = {
        str(spec.frontmatter.get("revision_id")): spec.frontmatter
        for spec in all_specs
        if optional_text(spec.frontmatter.get("revision_id"))
    }
    pending = normalize_list(amended.get("supersedes"))
    superseded: set[str] = set()
    while pending:
        revision = pending.pop()
        if revision in superseded:
            continue
        superseded.add(revision)
        prior = by_revision.get(revision)
        if prior:
            pending.extend(normalize_list(prior.get("supersedes")))
    return superseded


def ticket_roots(vault_root: Path, project: str, client: str) -> list[Path]:
    """Return possible ticket directories for the project."""
    roots: list[Path] = []
    if client != "platform":
        roots.append(vault_root / "clients" / client / "tickets")
        roots.append(vault_root / "clients" / client / "snapshots" / project / "tickets")
    roots.append(vault_root / "tickets")
    roots.append(vault_root / project / "tickets")
    roots.append(vault_root / "snapshots" / project / "tickets")
    return roots


def discover_tickets(vault_root: Path, project: str, client: str) -> list[TicketRecord]:
    """Discover ticket markdown files for a project."""
    records: list[TicketRecord] = []
    seen: set[Path] = set()
    for root in ticket_roots(vault_root, project, client):
        if not root.exists():
            continue
        for path in sorted(root.glob("*.md")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            try:
                frontmatter, body = load_markdown(resolved)
            except Exception:
                continue
            if frontmatter.get("type") != "ticket":
                continue
            if optional_text(frontmatter.get("project")) not in {None, project}:
                continue
            seen.add(resolved)
            records.append(TicketRecord(path=resolved, frontmatter=frontmatter, body=body))
    return records


def resolve_reference_path(raw: Any, vault_root: Path) -> Path | None:
    """Resolve a stored visual_spec_path."""
    text = str(raw or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_absolute():
        return path.resolve()
    candidates = [
        (vault_root.parent / path).resolve(),
        (vault_root / path).resolve(),
        (REPO_ROOT / path).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def revision_for_visual_spec_path(raw: Any, vault_root: Path) -> str | None:
    """Return revision_id for a stored visual_spec_path when possible."""
    path = resolve_reference_path(raw, vault_root)
    if not path or not path.exists():
        return None
    try:
        frontmatter, _ = load_markdown(path)
    except Exception:
        return None
    return optional_text(frontmatter.get("revision_id"))


def ticket_visual_spec_revision(ticket: TicketRecord, vault_root: Path) -> str | None:
    """Read the visual-spec revision referenced by a ticket."""
    direct = optional_text(ticket.frontmatter.get("visual_spec_revision_id")) or optional_text(
        ticket.frontmatter.get("visual_spec_revision")
    )
    if direct:
        return direct
    return revision_for_visual_spec_path(ticket.frontmatter.get("visual_spec_path"), vault_root)


def classify_ticket(ticket: TicketRecord) -> str:
    """Classify a ticket into the amendment invalidation state machine."""
    status = str(ticket.frontmatter.get("status") or "").strip().lower()
    task_type = str(ticket.frontmatter.get("task_type") or "general").strip().lower()
    executor_state = str(ticket.frontmatter.get("executor_state") or "").strip().lower()
    if task_type == "delivery" and status == "closed":
        return "past_delivery_gate"
    if status == "closed" and task_type in REVIEW_TASK_TYPES:
        return "closed_review_complete"
    if status == "closed" and task_type in BUILD_TASK_TYPES:
        return "closed_build_complete"
    if executor_state == "running" or status == "in-progress":
        return "open_in_progress"
    if status == "open" and executor_state in {"", "not_started", "not-started"}:
        return "open_not_started"
    return f"{status or 'unknown'}_{executor_state or 'idle'}"


def is_review_ticket(ticket: TicketRecord) -> bool:
    """Return whether a ticket is a review-like downstream ticket."""
    task_type = str(ticket.frontmatter.get("task_type") or "").strip().lower()
    title = str(ticket.frontmatter.get("title") or "").lower()
    return task_type in REVIEW_TASK_TYPES or "review" in title or "quality" in title


def downstream_review_tickets(source: TicketRecord, tickets: list[TicketRecord]) -> list[TicketRecord]:
    """Find downstream review tickets that are blocked by or remediate a source build ticket."""
    source_id = optional_text(source.frontmatter.get("id"))
    if not source_id:
        return []
    downstream: list[TicketRecord] = []
    for ticket in tickets:
        if ticket.path == source.path or not is_review_ticket(ticket):
            continue
        blockers = set(normalize_list(ticket.frontmatter.get("blocked_by")))
        remediation_for = optional_text(ticket.frontmatter.get("remediation_for"))
        if source_id in blockers or remediation_for == source_id:
            downstream.append(ticket)
    return downstream


def path_to_store(path: Path, vault_root: Path, old_value: Any) -> str:
    """Store paths in the existing ticket style when possible."""
    if str(old_value or "").strip().startswith("/"):
        return str(path.resolve())
    try:
        return str(path.resolve().relative_to(vault_root.parent))
    except ValueError:
        return str(path.resolve())


def invalidation_record(
    ticket: TicketRecord,
    state: str,
    action: str,
    old_revision: str | None,
    new_revision: str,
) -> dict[str, Any]:
    """Build a standard invalidation record."""
    return {
        "ticket_path": str(ticket.path.resolve()),
        "ticket_id": optional_text(ticket.frontmatter.get("id")),
        "ticket_state_before": state,
        "amendment_action": action,
        "old_vs_revision": old_revision,
        "new_vs_revision": new_revision,
    }


def apply_updates(ticket: TicketRecord, updates: dict[str, Any]) -> None:
    """Atomically rewrite a ticket frontmatter block with updates applied."""
    updated_frontmatter = dict(ticket.frontmatter)
    updated_frontmatter.update(updates)
    text = "---\n" + yaml.safe_dump(updated_frontmatter, sort_keys=False, allow_unicode=True) + "---\n" + ticket.body
    tmp_path = ticket.path.with_name(f"{ticket.path.name}.tmp-{os.getpid()}-{time.monotonic_ns()}")
    with tmp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, ticket.path)
    try:
        dir_fd = os.open(str(ticket.path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def plan_invalidations(
    tickets: list[TicketRecord],
    superseded_revisions: set[str],
    amended_path: Path,
    amended_frontmatter: dict[str, Any],
    vault_root: Path,
) -> tuple[dict[str, Any], dict[Path, dict[str, Any]]]:
    """Build the invalidation report and optional frontmatter updates."""
    new_revision = str(amended_frontmatter["revision_id"])
    new_locked_at = iso_datetime_value(amended_frontmatter["tokens_locked_at"], "tokens_locked_at")
    affected_by_path = {ticket.path: ticket for ticket in tickets}
    updates: dict[Path, dict[str, Any]] = {}
    report = {
        "tickets_invalidated": [],
        "tickets_requiring_restart": [],
        "tickets_requiring_review_rerun": [],
        "tickets_blocking_delivery": [],
    }

    for ticket in tickets:
        old_revision = ticket_visual_spec_revision(ticket, vault_root)
        if old_revision not in superseded_revisions:
            continue
        state = classify_ticket(ticket)
        base_updates = {
            "visual_spec_amended_at": now_iso(),
            "visual_spec_old_revision_id": old_revision,
            "visual_spec_new_revision_id": new_revision,
        }
        if state == "open_not_started":
            old_path_value = ticket.frontmatter.get("visual_spec_path")
            ticket_updates = {
                **base_updates,
                "visual_spec_path": path_to_store(amended_path, vault_root, old_path_value),
                "visual_spec_locked_at": new_locked_at,
                "visual_spec_id": amended_frontmatter.get("visual_spec_id"),
                "visual_spec_revision_id": new_revision,
                "visual_spec_amendment_action": "auto_updated",
            }
            updates[ticket.path] = ticket_updates
            report["tickets_invalidated"].append(
                invalidation_record(ticket, state, "auto_updated", old_revision, new_revision)
            )
        elif state == "open_in_progress":
            ticket_updates = {
                **base_updates,
                "requires_restart": True,
                "visual_spec_amendment_pending": True,
                "visual_spec_amendment_action": "requires_restart",
            }
            updates[ticket.path] = ticket_updates
            record = invalidation_record(ticket, state, "requires_restart", old_revision, new_revision)
            report["tickets_invalidated"].append(record)
            report["tickets_requiring_restart"].append(record)
        elif state == "closed_build_complete":
            record = invalidation_record(ticket, state, "requires_downstream_review_rerun", old_revision, new_revision)
            report["tickets_invalidated"].append(record)
            updates[ticket.path] = {
                **base_updates,
                "visual_spec_amendment_pending": True,
                "visual_spec_amendment_action": "requires_downstream_review_rerun",
            }
            for downstream in downstream_review_tickets(ticket, tickets):
                downstream_updates = {
                    "requires_review_rerun": True,
                    "visual_spec_amendment_pending": True,
                    "visual_spec_amendment_action": "requires_review_rerun",
                    "visual_spec_amended_at": now_iso(),
                    "visual_spec_old_revision_id": old_revision,
                    "visual_spec_new_revision_id": new_revision,
                }
                updates[downstream.path] = {**updates.get(downstream.path, {}), **downstream_updates}
                downstream_record = invalidation_record(
                    downstream,
                    classify_ticket(downstream),
                    "requires_review_rerun",
                    ticket_visual_spec_revision(downstream, vault_root),
                    new_revision,
                )
                report["tickets_requiring_review_rerun"].append(downstream_record)
        elif state == "closed_review_complete":
            ticket_updates = {
                **base_updates,
                "requires_review_rerun": True,
                "visual_spec_amendment_pending": True,
                "visual_spec_amendment_action": "requires_review_rerun",
            }
            updates[ticket.path] = ticket_updates
            record = invalidation_record(ticket, state, "requires_review_rerun", old_revision, new_revision)
            report["tickets_invalidated"].append(record)
            report["tickets_requiring_review_rerun"].append(record)
        elif state == "past_delivery_gate":
            ticket_updates = {
                **base_updates,
                "requires_visual_recheck": True,
                "delivery_blocked": True,
                "visual_spec_amendment_pending": True,
                "visual_spec_amendment_action": "requires_visual_recheck",
            }
            updates[ticket.path] = ticket_updates
            record = invalidation_record(ticket, state, "requires_visual_recheck", old_revision, new_revision)
            report["tickets_invalidated"].append(record)
            report["tickets_blocking_delivery"].append(record)
        else:
            ticket_updates = {
                **base_updates,
                "visual_spec_amendment_pending": True,
                "visual_spec_amendment_action": "manual_review",
            }
            updates[ticket.path] = ticket_updates
            report["tickets_invalidated"].append(
                invalidation_record(ticket, state, "manual_review", old_revision, new_revision)
            )

    # Keep the dict referenced so linters do not mistake the ticket index as dead state in future edits.
    _ = affected_by_path
    return report, updates


def emit(payload: dict[str, Any], json_out: str | None) -> None:
    """Emit JSON to stdout and optionally to a file."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Run amendment invalidation detection or application."""
    amended_path = Path(args.vs_path).expanduser().resolve()
    if not amended_path.exists():
        raise FileNotFoundError(f"amended VS path does not exist: {amended_path}")
    vault_root = resolve_vault_root(args.vault_root, amended_path)
    validate_visual_spec(amended_path, vault_root)
    amended_frontmatter, _ = load_markdown(amended_path)
    client = infer_client(amended_path, vault_root, args.client)
    all_specs = discover_visual_specs(vault_root, args.project, client, amended_path)
    superseded_revisions = collect_superseded_revisions(amended_frontmatter, all_specs)
    tickets = discover_tickets(vault_root, args.project, client)
    plan, updates = plan_invalidations(tickets, superseded_revisions, amended_path, amended_frontmatter, vault_root)

    if args.action == "apply":
        ticket_by_path = {ticket.path: ticket for ticket in tickets}
        for path, ticket_updates in updates.items():
            apply_updates(ticket_by_path[path], ticket_updates)
        bump_generation(vault_root)

    return {
        "amended_vs_path": str(amended_path),
        "amended_at": iso_datetime_value(amended_frontmatter.get("tokens_locked_at"), "tokens_locked_at"),
        "amendment_action": args.action,
        "tickets_scanned": len(tickets),
        **plan,
    }


def main() -> int:
    """Run the CLI."""
    args = parse_args()
    try:
        emit(run(args), args.json_out)
        return 0
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        print(f"subprocess failed: {stderr}", file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
