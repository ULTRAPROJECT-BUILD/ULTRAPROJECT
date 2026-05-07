#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLATFORM_PATH = REPO_ROOT / "vault" / "config" / "platform.md"


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


def _find_agent_enabled_line(lines: list[str], block_start: int, block_end: int, agent_name: str) -> int | None:
    in_agents = False
    current_agent = None
    for idx in range(block_start, block_end):
        raw_line = lines[idx]
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if indent == 2 and stripped == "agents:":
            in_agents = True
            current_agent = None
            continue
        if indent == 2 and stripped.endswith(":") and stripped != "agents:":
            if in_agents:
                break
        if not in_agents:
            continue
        if indent == 4 and stripped.endswith(":"):
            current_agent = stripped[:-1]
            continue
        if current_agent == agent_name and indent == 6 and stripped.startswith("enabled:"):
            return idx
    return None


def read_claude_enabled(platform_path: Path) -> bool:
    block = extract_agent_routing_block(platform_path.read_text(encoding="utf-8"))
    if block is None:
        raise SystemExit(f"Could not locate '## Agent Routing' YAML block in {platform_path}")
    block_start, block_end, lines = block
    idx = _find_agent_enabled_line(lines, block_start, block_end, "claude")
    if idx is None:
        raise SystemExit(f"Could not locate 'claude.enabled' in {platform_path}")
    value = lines[idx].split(":", 1)[1].split("#", 1)[0].strip().lower()
    return value == "true"


def write_claude_enabled(platform_path: Path, enabled: bool) -> None:
    text = platform_path.read_text(encoding="utf-8")
    block = extract_agent_routing_block(text)
    if block is None:
        raise SystemExit(f"Could not locate '## Agent Routing' YAML block in {platform_path}")
    block_start, block_end, lines = block
    idx = _find_agent_enabled_line(lines, block_start, block_end, "claude")
    if idx is None:
        raise SystemExit(f"Could not locate 'claude.enabled' in {platform_path}")
    lines[idx] = f"      enabled: {'true' if enabled else 'false'}\n"
    platform_path.write_text("".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Temporarily mark Claude as available or unavailable in platform routing."
    )
    parser.add_argument(
        "state",
        nargs="?",
        choices=("up", "down"),
        help="Set Claude available (up) or unavailable (down). Omit to print the current state.",
    )
    parser.add_argument(
        "--platform",
        type=Path,
        default=DEFAULT_PLATFORM_PATH,
        help="Path to platform.md",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    platform_path = args.platform.resolve()
    if not platform_path.exists():
        raise SystemExit(f"Platform config not found: {platform_path}")

    current_enabled = read_claude_enabled(platform_path)
    if args.state is None:
        print("up" if current_enabled else "down")
        return 0

    target_enabled = args.state == "up"
    write_claude_enabled(platform_path, target_enabled)
    print(f"{'up' if current_enabled else 'down'} -> {'up' if target_enabled else 'down'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
