#!/usr/bin/env python3
"""ULTRAPROJECT — drop in your specs, prompt, and walk away.

This module is the user-facing CLI. It does one job: bootstrap.

    ultraproject              # bootstrap config + show readiness
    ultraproject --version    # print version

Bootstrap copies `.env.example` -> `.env`, `.mcp.example.json` -> `.mcp.json`,
and `vault/clients/_registry.example.md` -> `vault/clients/_registry.md` if any
of the targets are missing, then verifies that `claude` or `codex` is on PATH.

Project execution is chat-native: open Claude Code or Codex pointed at the
repo and paste the orchestrator prompt from README.md. The CLI is bootstrap-only.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

VERSION = "1.0.0"

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

RAINBOW = [196, 202, 208, 214, 220, 226, 154, 118, 82, 46, 49, 51, 45, 39, 33, 27, 57, 93, 129, 165, 201]


def _color(code: int) -> str:
    return f"\033[38;5;{code}m"


GREEN_OK = _color(46)
BLUE = _color(39)
YELLOW = _color(214)
RED = _color(196)


def _supports_color() -> bool:
    return sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"{code}{text}{RESET}"


_BLOCK_BANNER = (
    "██╗   ██╗██╗  ████████╗██████╗  █████╗ ██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗\n"
    "██║   ██║██║  ╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝\n"
    "██║   ██║██║     ██║   ██████╔╝███████║██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║   \n"
    "██║   ██║██║     ██║   ██╔══██╗██╔══██║██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║   \n"
    "╚██████╔╝███████╗██║   ██║  ██║██║  ██║██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║   \n"
    " ╚═════╝ ╚══════╝╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝   "
)
_BANNER_WIDTH = 96


def _rainbow_line(line: str, width: int) -> str:
    """Color each non-space cell with a horizontal rainbow gradient."""
    out = []
    last_idx = -1
    for col, ch in enumerate(line):
        if ch == " ":
            out.append(" ")
            continue
        idx = min((col * len(RAINBOW)) // max(width, 1), len(RAINBOW) - 1)
        if idx != last_idx:
            out.append(_color(RAINBOW[idx]) + BOLD)
            last_idx = idx
        out.append(ch)
    out.append(RESET)
    return "".join(out)


def banner() -> None:
    cols = shutil.get_terminal_size(fallback=(80, 24)).columns
    print()
    if not _supports_color() or cols < _BANNER_WIDTH:
        # narrow terminal or piped output → single-line title fallback
        title = "ULTRAPROJECT"
        if _supports_color():
            styled = ""
            for i, ch in enumerate(title):
                color_code = RAINBOW[(i * len(RAINBOW) // len(title)) % len(RAINBOW)]
                styled += f"{_color(color_code)}{BOLD}{ch}"
            styled += RESET
        else:
            styled = title
        print(f"  {styled}")
    else:
        for line in _BLOCK_BANNER.split("\n"):
            print(_rainbow_line(line, _BANNER_WIDTH))
    print()


def print_intro() -> None:
    print(f"{_c('ULTRAPROJECT', BOLD)} {_c('v' + VERSION, BLUE)}")
    print()
    print("Drop in your specs, prompt, and walk away.")
    print("Projects run for hours, days, weeks, or more if needed.")
    print("Built for maximum quality, not quick responses.")
    print()
    print(f"{_c('✓', GREEN_OK)} Durable memory in vault/")
    print(f"{_c('✓', GREEN_OK)} Agents plan, build, review, and verify each other")
    print(f"{_c('✓', GREEN_OK)} No manual bug hunting. Review once done.")
    print()


def repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default cwd) looking for the repo markers.

    A directory is considered the ultraproject repo root if it contains both
    `SYSTEM.md` and a `vault/` directory. Falls back to cwd if no marker is
    found, so the bootstrap can still copy example files when run from inside
    a freshly cloned repo with the markers in place.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "SYSTEM.md").exists() and (candidate / "vault").is_dir():
            return candidate
    # cwd has no markers — fall back to walking up from the installed
    # script's location so `ultraproject` works from any directory after a
    # global install (e.g. via pipx from a cloned repo).
    script_dir = Path(__file__).resolve().parent
    for candidate in (script_dir, *script_dir.parents):
        if (candidate / "SYSTEM.md").exists() and (candidate / "vault").is_dir():
            return candidate
    return here


def copy_if_missing(src: Path, dest: Path) -> bool:
    if dest.exists() or not src.exists():
        return False
    shutil.copy2(src, dest)
    return True


def bootstrap_configs(root: Path) -> list[Path]:
    pairs = [
        (root / ".env.example", root / ".env"),
        (root / ".mcp.example.json", root / ".mcp.json"),
        (
            root / "vault" / "clients" / "_registry.example.md",
            root / "vault" / "clients" / "_registry.md",
        ),
    ]
    created: list[Path] = []
    for src, dest in pairs:
        if copy_if_missing(src, dest):
            created.append(dest)
    return created


def detect_clis() -> tuple[bool, bool]:
    return shutil.which("claude") is not None, shutil.which("codex") is not None


def cmd_bootstrap(args: argparse.Namespace) -> int:
    root = repo_root()
    banner()
    print_intro()

    created = bootstrap_configs(root)
    for path in created:
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        print(f"  {_c('created', DIM)} {rel}")
    if created:
        print()

    has_claude, has_codex = detect_clis()
    if not has_claude and not has_codex:
        print(f"{_c('!', YELLOW)} Neither {_c('claude', BOLD)} nor {_c('codex', BOLD)} found on PATH.")
        print(f"  Install Claude Code:  https://claude.com/claude-code")
        print(f"  or Codex CLI:         https://github.com/openai/codex")
        print()
    else:
        detected = ", ".join(name for name, present in (("claude", has_claude), ("codex", has_codex)) if present)
        print(f"  Detected: {_c(detected, BOLD)}")
        print()

    done = _c("Done!", GREEN_OK)
    system_md = _c("SYSTEM.md", BLUE)
    schema_md = _c("vault/SCHEMA.md", BLUE)
    print(f"{done} Open {system_md} and {schema_md} to begin.")
    print()
    print(f"  {_c('Next step:', BOLD)} open Claude Code or Codex pointed at this repo, then paste:")
    print()
    print(f"    {_c('Read SYSTEM.md and skills/orchestrator.md — especially the', DIM)}")
    print(f"    {_c('Critical Rules block at the top of orchestrator.md, those are', DIM)}")
    print(f"    {_c('load-bearing. Follow the skill literally.', DIM)}")
    print(f"    {_c('Here is what I want to build: <your prompt>.', DIM)}")
    print(f"    {_c('Be strict about acceptance criteria, run to completion — do not', DIM)}")
    print(f"    {_c('stop, pause, or ask clarifying questions unless I explicitly', DIM)}")
    print(f"    {_c('tell you otherwise.', DIM)}")
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ultraproject",
        description="ULTRAPROJECT — bootstrap config and check readiness. "
        "Project execution is chat-native — see README.md.",
    )
    parser.add_argument(
        "--version", action="version", version=f"ultraproject {VERSION}"
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser(
        "init",
        help="Bootstrap config files and check readiness (default if no command given).",
    )

    parser.parse_args(argv)
    return cmd_bootstrap(argparse.Namespace())


if __name__ == "__main__":
    raise SystemExit(main())
