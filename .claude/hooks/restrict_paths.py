#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def platform_dir() -> Path:
    return Path(
        os.environ.get("PLATFORM_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or Path.cwd()
    ).resolve()


def normalize(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def is_within(child: Path, parent: Path) -> bool:
    child_text = normalize(child)
    parent_text = normalize(parent)
    try:
        return os.path.commonpath([child_text, parent_text]) == parent_text
    except ValueError:
        return False


def blocked(message: str) -> int:
    print(f"BLOCKED: {message}", file=sys.stderr)
    return 2


def load_payload() -> dict:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_paths(payload: dict) -> list[str]:
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    if tool_name == "MultiEdit":
        return [
            edit.get("file_path", "")
            for edit in tool_input.get("edits", [])
            if edit.get("file_path")
        ]
    path = tool_input.get("file_path", "")
    return [path] if path else []


def restricted_exact_files(root: Path) -> set[str]:
    files = [
        root / ".mcp.json",
        root / ".env",
        root / ".financial-secrets",
        root / "SYSTEM.md",
        root / "CLAUDE.md",
        root / "overnight-review.sh",
        root / "vault" / "config" / "platform.md",
        root / "vault" / "config" / ".spending-integrity",
    ]
    return {normalize(path) for path in files}


def restricted_dirs(root: Path) -> list[Path]:
    return [
        root / "skills",
        root / "scripts",
        root / ".claude" / "hooks",
    ]


def main() -> int:
    payload = load_payload()
    tool_name = payload.get("tool_name", "")
    if tool_name not in WRITE_TOOLS:
        return 0

    root = platform_dir()
    exact_files = restricted_exact_files(root)
    dir_prefixes = restricted_dirs(root)
    settings_path = root / ".claude" / "settings.json"

    for raw_path in write_paths(payload):
        target = Path(raw_path).expanduser().resolve()
        if not is_within(target, root):
            return blocked(f"File writes are restricted to the platform directory. Attempted write to: {raw_path}")

        target_text = normalize(target)
        if target_text in exact_files or target_text == normalize(settings_path):
            return blocked(f"'{target.name}' is restricted infrastructure. Agents cannot modify it.")

        for restricted_dir in dir_prefixes:
            if is_within(target, restricted_dir):
                return blocked(f"Writes to {restricted_dir} are admin-only. Agents cannot modify files there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
