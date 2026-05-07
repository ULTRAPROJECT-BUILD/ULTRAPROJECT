#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

VALID_MODES = {"normal", "codex_fallback", "claude_fallback", "chat_native"}


def extract_agent_routing_block(text: str) -> tuple[int, int, list[str]] | None:
    lines = text.splitlines(keepends=True)
    heading_idx = None
    block_start = None
    block_end = None
    for idx, line in enumerate(lines):
        if line.strip() == "## Agent Routing":
            heading_idx = idx
            break
    if heading_idx is None:
        return None
    for idx in range(heading_idx + 1, len(lines)):
        if lines[idx].strip() == "```yaml":
            block_start = idx + 1
            break
    if block_start is None:
        return None
    for idx in range(block_start, len(lines)):
        if lines[idx].strip() == "```":
            block_end = idx
            break
    if block_end is None:
        return None
    return block_start, block_end, lines


def read_agent_mode(platform_path: Path) -> str:
    block = extract_agent_routing_block(platform_path.read_text(encoding="utf-8"))
    if block is None:
        raise SystemExit(f"Could not locate '## Agent Routing' YAML block in {platform_path}")
    block_start, block_end, lines = block
    for raw_line in lines[block_start:block_end]:
        stripped = raw_line.strip()
        if stripped.startswith("agent_mode:"):
            value = stripped.split(":", 1)[1].split("#", 1)[0].strip()
            return value or "chat_native"
    return "chat_native"


def write_agent_mode(platform_path: Path, mode: str) -> None:
    if mode not in VALID_MODES:
        raise SystemExit(f"Unsupported mode '{mode}'. Expected one of: {', '.join(sorted(VALID_MODES))}")

    text = platform_path.read_text(encoding="utf-8")
    block = extract_agent_routing_block(text)
    if block is None:
        raise SystemExit(f"Could not locate '## Agent Routing' YAML block in {platform_path}")
    block_start, block_end, lines = block

    updated = False
    for idx in range(block_start, block_end):
        stripped = lines[idx].strip()
        if stripped.startswith("agent_mode:"):
            lines[idx] = f"  agent_mode: {mode}\n"
            updated = True
            break

    if not updated:
        insert_at = None
        for idx in range(block_start, block_end):
            if lines[idx].strip() == "agent_routing:":
                insert_at = idx + 1
                break
        if insert_at is None:
            raise SystemExit(f"Could not locate 'agent_routing:' in {platform_path}")
        lines.insert(insert_at, f"  agent_mode: {mode}\n")

    platform_path.write_text("".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set or inspect the platform agent routing mode.")
    parser.add_argument("mode", nargs="?", choices=sorted(VALID_MODES), help="New mode to write. Omit to print the current mode.")
    parser.add_argument(
        "--platform",
        type=Path,
        default=REPO_ROOT / "vault" / "config" / "platform.md",
        help="Path to platform.md",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    platform_path = args.platform.resolve()
    if not platform_path.exists():
        raise SystemExit(f"Platform config not found: {platform_path}")

    if args.mode is None:
        print(read_agent_mode(platform_path))
        return 0

    previous = read_agent_mode(platform_path)
    write_agent_mode(platform_path, args.mode)
    print(f"{previous} -> {args.mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
