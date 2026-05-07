#!/usr/bin/env python3
"""
Verify a deliverable from a fresh copied workspace and emit evidence reports.

This script is intentionally narrow. It does not try to infer the "right"
commands from docs. The caller must provide the documented workflow as explicit
commands, then this script runs them in a clean copied directory, captures
results, checks expected artifacts, and writes machine-readable evidence.

Usage:
    python3 scripts/verify_release.py \
      --source /path/to/project \
      --command "npm ci" \
      --command "npm test" \
      --artifact README.md \
      --artifact dist/index.html \
      --json-out /tmp/fresh-checkout.json \
      --markdown-out /tmp/fresh-checkout.md
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
DEFAULT_TIMEOUT_SECONDS = 900
DEFAULT_IGNORED_NAMES = {
    ".DS_Store",
    ".git",
    ".idea",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
    ".venv",
    "__pycache__",
    "node_modules",
}
WARNING_RE = re.compile(r"\bwarning\b", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Directory to verify from a fresh copy.")
    parser.add_argument(
        "--workdir-subpath",
        default=".",
        help="Subdirectory within the copied source where commands should run.",
    )
    parser.add_argument(
        "--command",
        action="append",
        default=[],
        help="Shell command to run in the fresh copy. Repeat for multiple commands.",
    )
    parser.add_argument(
        "--command-file",
        help="Optional file containing one command per line. Blank lines and # comments are ignored.",
    )
    parser.add_argument(
        "--artifact",
        action="append",
        default=[],
        help="Artifact path or glob, relative to the copied source root. Repeat for multiple checks.",
    )
    parser.add_argument(
        "--warning-budget",
        type=int,
        default=None,
        help="Maximum allowed warning-line count across all commands. Omit to disable warning gating.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-command timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument("--json-out", help="Optional JSON report path.")
    parser.add_argument("--markdown-out", help="Optional Markdown report path.")
    parser.add_argument(
        "--keep-workdir",
        action="store_true",
        help="Keep the fresh copied workspace instead of deleting it after verification.",
    )
    return parser.parse_args()


def read_commands(args: argparse.Namespace) -> list[str]:
    commands = list(args.command)
    if args.command_file:
        command_path = Path(args.command_file)
        for raw_line in command_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            commands.append(line)
    return commands


def ignore_names(_: str, names: list[str]) -> list[str]:
    return [name for name in names if name in DEFAULT_IGNORED_NAMES]


def fresh_copy(source: Path) -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="verify-release."))
    copied_root = temp_root / source.name
    shutil.copytree(source, copied_root, ignore=ignore_names)
    return temp_root, copied_root


def count_warning_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if WARNING_RE.search(line))


def tail_text(text: str, max_lines: int = 20, max_chars: int = 4000) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    tail = "\n".join(lines[-max_lines:])
    if len(tail) > max_chars:
        tail = tail[-max_chars:]
    return tail


def run_command(command: str, cwd: Path, timeout_seconds: int) -> dict:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            executable="/bin/zsh",
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        stderr = f"{stderr}\n[verify_release] Timed out after {timeout_seconds}s.".strip()
        exit_code = 124
        timed_out = True

    duration_seconds = round(time.monotonic() - started, 2)
    combined = "\n".join(part for part in (stdout, stderr) if part)
    warning_count = count_warning_lines(combined)
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_seconds": duration_seconds,
        "warning_count": warning_count,
        "stdout_tail": tail_text(stdout),
        "stderr_tail": tail_text(stderr),
        "status": "PASS" if exit_code == 0 else "FAIL",
    }


def normalize_artifact_patterns(patterns: list[str]) -> list[tuple[str, str]]:
    normalized_patterns = []
    for raw_pattern in patterns:
        pattern = raw_pattern.strip()
        normalized = pattern[2:] if pattern.startswith("./") else pattern
        candidate = Path(normalized)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"Artifact patterns must stay within the copied source: {pattern}")
        normalized_patterns.append((pattern, normalized))
    return normalized_patterns


def check_artifacts(root: Path, patterns: list[tuple[str, str]]) -> list[dict]:
    results = []
    for original, normalized in patterns:
        matches = sorted(
            str(path.relative_to(root))
            for path in root.glob(normalized)
        )
        results.append(
            {
                "pattern": original,
                "matches": matches,
                "ok": bool(matches),
            }
        )
    return results


def build_report(
    args: argparse.Namespace,
    source: Path,
    copied_root: Path,
    command_results: list[dict],
    artifact_results: list[dict],
) -> dict:
    total_warnings = sum(result["warning_count"] for result in command_results)
    commands_ok = all(result["exit_code"] == 0 for result in command_results)
    artifacts_ok = all(result["ok"] for result in artifact_results)
    warning_budget_ok = (
        True
        if args.warning_budget is None
        else total_warnings <= args.warning_budget
    )

    verdict = "PASS" if commands_ok and artifacts_ok and warning_budget_ok else "FAIL"
    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "source": str(source.resolve()),
        "fresh_copy_root": str(copied_root),
        "workdir_subpath": args.workdir_subpath,
        "warning_budget": args.warning_budget,
        "commands": command_results,
        "artifacts": artifact_results,
        "summary": {
            "commands_passed": sum(1 for result in command_results if result["exit_code"] == 0),
            "commands_total": len(command_results),
            "artifacts_passed": sum(1 for result in artifact_results if result["ok"]),
            "artifacts_total": len(artifact_results),
            "total_warning_lines": total_warnings,
            "warning_budget_ok": warning_budget_ok,
        },
        "verdict": verdict,
    }


def render_markdown(report: dict) -> str:
    lines = [
        f"# Release Verification — {Path(report['source']).name}",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Source:** {report['source']}",
        f"**Fresh copy root:** {report['fresh_copy_root']}",
        f"**Workdir subpath:** {report['workdir_subpath']}",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Summary",
        "",
        f"- Commands: {report['summary']['commands_passed']}/{report['summary']['commands_total']} passed",
        f"- Artifacts: {report['summary']['artifacts_passed']}/{report['summary']['artifacts_total']} present",
        f"- Warning lines: {report['summary']['total_warning_lines']}",
    ]
    if report["warning_budget"] is not None:
        lines.append(f"- Warning budget: {report['warning_budget']} ({'PASS' if report['summary']['warning_budget_ok'] else 'FAIL'})")

    lines.extend(
        [
            "",
            "## Command Results",
            "",
            "| Command | Exit | Duration (s) | Warnings | Status |",
            "|---------|------|--------------|----------|--------|",
        ]
    )
    for result in report["commands"]:
        lines.append(
            f"| `{result['command']}` | {result['exit_code']} | {result['duration_seconds']} | {result['warning_count']} | {result['status']} |"
        )

    if report["commands"]:
        lines.extend(["", "## Command Excerpts", ""])
        for index, result in enumerate(report["commands"], start=1):
            lines.append(f"### Command {index}")
            lines.append("")
            lines.append(f"`{result['command']}`")
            lines.append("")
            if result["stdout_tail"]:
                lines.append("**stdout tail**")
                lines.append("")
                lines.append("```text")
                lines.append(result["stdout_tail"])
                lines.append("```")
            if result["stderr_tail"]:
                lines.append("**stderr tail**")
                lines.append("")
                lines.append("```text")
                lines.append(result["stderr_tail"])
                lines.append("```")
            if not result["stdout_tail"] and not result["stderr_tail"]:
                lines.append("_No output captured._")
            lines.append("")

    lines.extend(
        [
            "## Artifact Checks",
            "",
            "| Pattern | Matches | Status |",
            "|---------|---------|--------|",
        ]
    )
    for result in report["artifacts"]:
        matches = "<br>".join(result["matches"]) if result["matches"] else "—"
        lines.append(
            f"| `{result['pattern']}` | {matches} | {'PASS' if result['ok'] else 'FAIL'} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def ensure_parent(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    path = Path(path_str).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def should_keep_temp(temp_root: Path, output_paths: list[Path | None], keep_requested: bool) -> bool:
    if keep_requested:
        return True
    for output_path in output_paths:
        if output_path and output_path.is_relative_to(temp_root):
            return True
    return False


def resolve_workdir(copied_root: Path, workdir_subpath: str) -> Path:
    candidate = Path(workdir_subpath)
    if candidate.is_absolute():
        raise ValueError("--workdir-subpath must be relative to the copied source.")

    resolved_root = copied_root.resolve()
    resolved = (copied_root / candidate).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("--workdir-subpath must stay within the copied source.")
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"--workdir-subpath does not exist inside copied source: {workdir_subpath}")
    return resolved


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        print(f"--source must be an existing directory: {source}", file=sys.stderr)
        return 2

    commands = read_commands(args)
    if not commands and not args.artifact:
        print("Provide at least one --command or --artifact.", file=sys.stderr)
        return 2

    temp_root, copied_root = fresh_copy(source)
    try:
        workdir = resolve_workdir(copied_root, args.workdir_subpath)
        artifact_patterns = normalize_artifact_patterns(args.artifact)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        shutil.rmtree(temp_root, ignore_errors=True)
        return 2

    command_results = [run_command(command, workdir, args.timeout_seconds) for command in commands]
    artifact_results = check_artifacts(copied_root, artifact_patterns)
    report = build_report(args, source, copied_root, command_results, artifact_results)

    json_out = ensure_parent(args.json_out)
    markdown_out = ensure_parent(args.markdown_out)
    markdown_text = render_markdown(report)

    if json_out:
        json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if markdown_out:
        markdown_out.write_text(markdown_text, encoding="utf-8")

    keep_temp = should_keep_temp(temp_root, [json_out, markdown_out], args.keep_workdir)
    if not keep_temp:
        shutil.rmtree(temp_root, ignore_errors=True)

    print(f"verdict={report['verdict']}")
    print(f"commands_passed={report['summary']['commands_passed']}/{report['summary']['commands_total']}")
    print(f"artifacts_passed={report['summary']['artifacts_passed']}/{report['summary']['artifacts_total']}")
    print(f"warning_lines={report['summary']['total_warning_lines']}")
    if json_out:
        print(f"json_report={json_out}")
    if markdown_out:
        print(f"markdown_report={markdown_out}")
    if keep_temp:
        print(f"fresh_copy_root={copied_root}")

    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
