#!/usr/bin/env python3
"""Verify a ticket's recorded visual-spec resolver generation is current."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-path", required=True, help="Ticket markdown path to check.")
    parser.add_argument("--json-out", help="Optional path to write JSON output.")
    parser.add_argument("--vault-root", help="Optional vault root override; useful for isolated tests.")
    return parser.parse_args()


def split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    """Split markdown frontmatter from body."""
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


def load_frontmatter(path: Path) -> dict[str, Any]:
    """Load YAML frontmatter from a markdown file."""
    frontmatter_text, _ = split_frontmatter(path.read_text(encoding="utf-8"), path)
    data = yaml.safe_load(frontmatter_text)
    return data if isinstance(data, dict) else {}


def optional_text(value: Any) -> str | None:
    """Normalize an optional scalar."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def int_value(value: Any, default: int = 0) -> int:
    """Parse an integer frontmatter value with a default."""
    if value is None or str(value).strip() == "":
        return default
    return int(value)


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


def infer_client(ticket_path: Path, vault_root: Path) -> str | None:
    """Infer client slug from a ticket path."""
    try:
        rel = ticket_path.resolve().relative_to(vault_root)
    except ValueError:
        return None
    parts = rel.parts
    if len(parts) >= 3 and parts[0] == "clients":
        return parts[1]
    return None


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


def resolve_reference_path(raw: Any, vault_root: Path) -> str | None:
    """Resolve a stored visual_spec_path for comparison."""
    text = str(raw or "").strip()
    if not text:
        return None
    path = Path(text).expanduser()
    if path.is_absolute():
        return str(path.resolve())
    candidates = [
        (vault_root.parent / path).resolve(),
        (vault_root / path).resolve(),
        (REPO_ROOT / path).resolve(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


def run_resolver(ticket_path: Path, ticket_frontmatter: dict[str, Any], vault_root: Path) -> dict[str, Any]:
    """Run resolve_visual_spec.py for a ticket."""
    project = optional_text(ticket_frontmatter.get("project"))
    if not project:
        raise ValueError(f"{ticket_path} is missing project frontmatter")
    command = [
        sys.executable,
        str(SCRIPT_DIR / "resolve_visual_spec.py"),
        "--ticket-path",
        str(ticket_path),
        "--project",
        project,
        "--vault-root",
        str(vault_root),
    ]
    client = infer_client(ticket_path, vault_root)
    if client:
        command.extend(["--client", client])
    phase = optional_text(ticket_frontmatter.get("phase"))
    if phase:
        command.extend(["--phase", phase])
    wave = optional_text(ticket_frontmatter.get("wave"))
    if wave:
        command.extend(["--wave", wave])
    env = {**os.environ, "ONESHOT_VAULT_ROOT": str(vault_root)}
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    result.check_returncode()
    return json.loads(result.stdout or "{}")


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Build the resolver-generation check payload."""
    ticket_path = Path(args.ticket_path).expanduser().resolve()
    if not ticket_path.exists():
        raise FileNotFoundError(f"ticket path does not exist: {ticket_path}")
    vault_root = resolve_vault_root(args.vault_root, ticket_path)
    frontmatter = load_frontmatter(ticket_path)
    ticket_generation = int_value(frontmatter.get("resolver_generation"), 0)
    current_generation = get_generation(vault_root)
    consistent = ticket_generation == current_generation
    old_path = resolve_reference_path(frontmatter.get("visual_spec_path"), vault_root)
    old_revision = optional_text(frontmatter.get("visual_spec_revision_id")) or optional_text(
        frontmatter.get("visual_spec_revision")
    )
    new_path = old_path
    new_revision = old_revision
    ticket_resolution_stale = False

    if not consistent:
        resolution = run_resolver(ticket_path, frontmatter, vault_root)
        new_path = resolution.get("resolved_vs_path")
        new_revision = resolution.get("resolved_revision_id")
        ticket_resolution_stale = (old_path != new_path) or (old_revision != new_revision)

    if consistent:
        recommended_action = "none"
    elif ticket_resolution_stale:
        recommended_action = "restart"
    else:
        recommended_action = "reresolve"

    return {
        "ticket_path": str(ticket_path),
        "ticket_resolver_generation": ticket_generation,
        "current_resolver_generation": current_generation,
        "consistent": consistent,
        "ticket_resolution_stale": ticket_resolution_stale,
        "resolved_vs_path_at_ticket_spawn": old_path,
        "resolved_vs_path_now": new_path,
        "recommended_action": recommended_action,
    }


def emit(payload: dict[str, Any], json_out: str | None) -> None:
    """Emit JSON to stdout and optionally to a file."""
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)


def main() -> int:
    """Run the CLI."""
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
