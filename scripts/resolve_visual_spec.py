#!/usr/bin/env python3
"""Resolve the locked visual specification that governs a ticket."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema
except ImportError as exc:  # pragma: no cover - dependency gate
    raise SystemExit("resolve_visual_spec.py requires jsonschema. Install with: python3 -m pip install jsonschema") from exc

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
VS_SCHEMA = REPO_ROOT / "schemas" / "visual-spec-frontmatter.schema.json"
OUTPUT_SCHEMA = REPO_ROOT / "schemas" / "resolver-output.schema.json"


@dataclass(frozen=True)
class VisualSpec:
    """A discovered visual specification revision."""

    path: Path
    frontmatter: dict[str, Any]
    tokens_locked_at: datetime


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-path", required=True, help="Ticket markdown path to resolve.")
    parser.add_argument("--project", required=True, help="Project slug.")
    parser.add_argument("--client", help="Client slug. Omit for platform/internal work.")
    parser.add_argument("--phase", help="Phase number or identifier override.")
    parser.add_argument("--wave", help="Wave identifier override.")
    parser.add_argument("--rerun", action="store_true", help="Re-resolve all tickets with existing visual_spec_path.")
    parser.add_argument("--json-out", help="Optional path to write resolver output JSON.")
    parser.add_argument("--vault-root", help="Optional vault root override; useful for isolated tests.")
    return parser.parse_args()


def now_iso() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def parse_datetime(value: Any, field_name: str) -> datetime:
    """Parse a YAML/JSON timestamp as an aware UTC datetime."""
    if isinstance(value, datetime):
        parsed = value
    elif value is None or str(value).strip() == "":
        raise ValueError(f"{field_name} is missing")
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def optional_text(value: Any) -> str | None:
    """Normalize an optional scalar for JSON output and matching."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    """Split a markdown document into YAML frontmatter and body."""
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
    frontmatter = "".join(lines[1:closing_index])
    body = "".join(lines[closing_index + 1 :])
    return frontmatter, body


def load_frontmatter(path: Path) -> dict[str, Any]:
    """Load YAML frontmatter from a markdown file."""
    frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8"), path)
    data = yaml.safe_load(frontmatter)
    return data if isinstance(data, dict) else {}


def resolve_vault_root(raw: str | None = None, anchor: Path | None = None) -> Path:
    """Resolve the active vault root from an override, anchor path, environment, or cwd."""
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


def infer_client(ticket_path: Path, vault_root: Path, explicit_client: str | None) -> str:
    """Infer the client slug from a ticket path when no explicit client was supplied."""
    if explicit_client:
        return explicit_client
    try:
        rel = ticket_path.resolve().relative_to(vault_root)
    except ValueError:
        return "platform"
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "clients":
        return parts[1]
    return "platform"


def validate_visual_spec(path: Path, vault_root: Path) -> None:
    """Validate a visual-spec frontmatter block through validate_schema.py."""
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


def get_generation(vault_root: Path) -> int:
    """Read the current resolver generation via lock_visual_spec.py."""
    env = {**os.environ, "ONESHOT_VAULT_ROOT": str(vault_root)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "lock_visual_spec.py"), "get-generation"],
        capture_output=True,
        text=True,
        env=env,
    )
    result.check_returncode()
    payload = json.loads(result.stdout or "{}")
    return int(payload.get("generation", 0))


def search_roots(vault_root: Path, project: str, client: str | None) -> list[Path]:
    """Return visual-spec search roots in client then platform precedence order."""
    roots: list[Path] = []
    if client and client != "platform":
        roots.append(vault_root / "clients" / client / "snapshots" / project)
    roots.append(vault_root / "snapshots" / project)
    return roots


def discover_visual_specs(vault_root: Path, project: str, client: str | None) -> list[VisualSpec]:
    """Discover and validate locked visual-spec snapshots for a project."""
    specs: list[VisualSpec] = []
    seen: set[Path] = set()
    for root in search_roots(vault_root, project, client):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*-visual-spec-*.md")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            validate_visual_spec(resolved, vault_root)
            frontmatter = load_frontmatter(resolved)
            if frontmatter.get("project") != project:
                continue
            if frontmatter.get("tokens_locked") is not True:
                continue
            if frontmatter.get("active") is not True:
                continue
            if frontmatter.get("deprecated") is True:
                continue
            specs.append(
                VisualSpec(
                    path=resolved,
                    frontmatter=frontmatter,
                    tokens_locked_at=parse_datetime(frontmatter.get("tokens_locked_at"), "tokens_locked_at"),
                )
            )
    return specs


def list_value(value: Any) -> list[str]:
    """Normalize frontmatter scalar/list values to a string list."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    parsed = None
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [text]


def spec_sort_key(spec: VisualSpec) -> tuple[float, bool, bool, str]:
    """Sort newest locked revisions first with deterministic revision tie-breaks."""
    return (
        -spec.tokens_locked_at.timestamp(),
        spec.frontmatter.get("active") is not True,
        spec.frontmatter.get("deprecated") is True,
        str(spec.frontmatter.get("revision_id", "")),
    )


def choose_latest(candidates: list[VisualSpec]) -> VisualSpec | None:
    """Return the highest-precedence candidate from a scope group."""
    if not candidates:
        return None
    return sorted(candidates, key=spec_sort_key)[0]


def governs_ticket(spec: VisualSpec, ticket_id: str, ticket_path: Path) -> bool:
    """Return whether a VS explicitly governs the ticket."""
    governed = set(list_value(spec.frontmatter.get("governs_tickets")))
    if ticket_id in governed:
        return True
    if ticket_path.name in governed:
        return True
    return str(ticket_path) in governed or str(ticket_path.resolve()) in governed


def resolve_spec(
    ticket_path: Path,
    project: str,
    client: str,
    phase_override: str | None,
    wave_override: str | None,
    vault_root: Path,
) -> tuple[VisualSpec | None, str, str | None, str | None, dict[str, Any]]:
    """Resolve a ticket to the applicable visual spec and scope."""
    ticket_frontmatter = load_frontmatter(ticket_path)
    ticket_id = str(ticket_frontmatter.get("id") or ticket_path.stem)
    phase = optional_text(phase_override) or optional_text(ticket_frontmatter.get("phase"))
    wave = optional_text(wave_override) or optional_text(ticket_frontmatter.get("wave"))
    specs = discover_visual_specs(vault_root, project, client)

    ticket_candidates = [spec for spec in specs if governs_ticket(spec, ticket_id, ticket_path)]
    chosen = choose_latest(ticket_candidates)
    if chosen:
        return chosen, "ticket", phase, wave, ticket_frontmatter

    if wave:
        wave_candidates = [
            spec
            for spec in specs
            if spec.frontmatter.get("spec_scope") == "wave" and optional_text(spec.frontmatter.get("wave")) == wave
        ]
        chosen = choose_latest(wave_candidates)
        if chosen:
            return chosen, "wave", phase, wave, ticket_frontmatter

    if phase:
        phase_candidates = [
            spec
            for spec in specs
            if spec.frontmatter.get("spec_scope") == "phase" and optional_text(spec.frontmatter.get("phase")) == phase
        ]
        chosen = choose_latest(phase_candidates)
        if chosen:
            return chosen, "phase", phase, wave, ticket_frontmatter

    project_candidates = [spec for spec in specs if spec.frontmatter.get("spec_scope") == "project"]
    chosen = choose_latest(project_candidates)
    if chosen:
        return chosen, "project", phase, wave, ticket_frontmatter

    return None, "none", phase, wave, ticket_frontmatter


def freshness(chosen: VisualSpec | None, ticket_frontmatter: dict[str, Any]) -> str:
    """Compute whether a ticket predates the resolved visual-spec lock."""
    if chosen is None:
        return "none"
    created_raw = ticket_frontmatter.get("created_at", ticket_frontmatter.get("created"))
    if created_raw in (None, ""):
        return "stale"
    created_at = parse_datetime(created_raw, "ticket created_at")
    return "fresh" if chosen.tokens_locked_at <= created_at else "stale"


def resolve_reference_path(raw: Any, vault_root: Path) -> Path | None:
    """Resolve a stored visual_spec_path from absolute or vault-relative text."""
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


def revision_for_path(path: Path | None) -> str | None:
    """Read a visual-spec revision_id from a stored path when possible."""
    if path is None or not path.exists():
        return None
    try:
        return optional_text(load_frontmatter(path).get("revision_id"))
    except Exception:
        return None


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


def discover_tickets(vault_root: Path, project: str, client: str) -> list[Path]:
    """Find ticket markdown files for the requested project."""
    tickets: list[Path] = []
    seen: set[Path] = set()
    for root in ticket_roots(vault_root, project, client):
        if not root.exists():
            continue
        for path in sorted(root.glob("*.md")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            try:
                frontmatter = load_frontmatter(resolved)
            except Exception:
                continue
            if frontmatter.get("type") != "ticket":
                continue
            if optional_text(frontmatter.get("project")) not in {None, project}:
                continue
            seen.add(resolved)
            tickets.append(resolved)
    return tickets


def run_rerun(project: str, client: str, vault_root: Path) -> dict[str, Any]:
    """Re-resolve tickets that already recorded a visual_spec_path."""
    stale_tickets: list[dict[str, Any]] = []
    ticket_paths = discover_tickets(vault_root, project, client)
    scanned = len(ticket_paths)
    for ticket_path in ticket_paths:
        ticket_frontmatter = load_frontmatter(ticket_path)
        if not optional_text(ticket_frontmatter.get("visual_spec_path")):
            continue
        old_path = resolve_reference_path(ticket_frontmatter.get("visual_spec_path"), vault_root)
        old_revision = optional_text(ticket_frontmatter.get("visual_spec_revision_id")) or optional_text(
            ticket_frontmatter.get("visual_spec_revision")
        )
        old_revision = old_revision or revision_for_path(old_path)
        chosen, _, _, _, _ = resolve_spec(
            ticket_path,
            project,
            client,
            optional_text(ticket_frontmatter.get("phase")),
            optional_text(ticket_frontmatter.get("wave")),
            vault_root,
        )
        new_revision = optional_text(chosen.frontmatter.get("revision_id")) if chosen else None
        new_path = chosen.path if chosen else None
        if (old_path and new_path and old_path.resolve() != new_path.resolve()) or old_revision != new_revision:
            stale_tickets.append(
                {
                    "ticket_path": str(ticket_path.resolve()),
                    "old_vs_revision": old_revision,
                    "new_vs_revision": new_revision,
                }
            )
    return {"scanned_tickets": scanned, "stale_tickets": stale_tickets}


def validate_output(payload: dict[str, Any]) -> None:
    """Validate resolver output against schemas/resolver-output.schema.json."""
    schema = json.loads(OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        detail = "; ".join(f"{'/'.join(map(str, error.path)) or '/'}: {error.message}" for error in errors)
        raise ValueError(f"resolver output schema validation failed: {detail}")


def emit(payload: dict[str, Any], json_out: str | None) -> None:
    """Validate and emit JSON to stdout and optionally a file."""
    validate_output(payload)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve the requested ticket and build the output payload."""
    ticket_path = Path(args.ticket_path).expanduser().resolve()
    if not ticket_path.exists():
        raise FileNotFoundError(f"ticket path does not exist: {ticket_path}")
    vault_root = resolve_vault_root(args.vault_root, ticket_path)
    client = infer_client(ticket_path, vault_root, args.client)
    chosen, scope, phase, wave, ticket_frontmatter = resolve_spec(
        ticket_path,
        args.project,
        client,
        args.phase,
        args.wave,
        vault_root,
    )
    resolver_generation = get_generation(vault_root)
    payload: dict[str, Any] = {
        "ticket_path": str(ticket_path),
        "project": args.project,
        "client": client,
        "phase": phase,
        "wave": wave,
        "resolved_vs_path": str(chosen.path) if chosen else None,
        "resolved_vs_id": optional_text(chosen.frontmatter.get("visual_spec_id")) if chosen else None,
        "resolved_revision_id": optional_text(chosen.frontmatter.get("revision_id")) if chosen else None,
        "resolved_scope": scope,
        "resolved_at": now_iso(),
        "resolver_generation": resolver_generation,
        "freshness": freshness(chosen, ticket_frontmatter),
        "rerun_results": None,
    }
    if args.rerun:
        payload["rerun_results"] = run_rerun(args.project, client, vault_root)
    return payload


def main() -> int:
    """Run the visual-spec resolver."""
    args = parse_args()
    try:
        emit(build_payload(args), args.json_out)
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
