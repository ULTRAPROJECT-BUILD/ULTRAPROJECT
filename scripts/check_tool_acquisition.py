#!/usr/bin/env python3
"""
Run a functional tool acquisition canary from a catalog entry.

The canary spec lives at acquisition.canary_steps. Steps are structured and
executed without a shell. A functional canary must do more than ask a tool for
its version.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_CATALOG_DIR = REPO_ROOT / "vault" / "archive" / "tools-catalog"

UNSAFE_ARG_TOKENS = ("&&", "|", ";", "`", "$(", "\n")
VERSION_ARGS = {"--version", "-version", "-v", "version"}


def now_text() -> str:
    return datetime.now().astimezone().isoformat()


def load_entry(path: Path | None = None, *, catalog_dir: Path | None = None, tool_slug: str | None = None) -> dict[str, Any]:
    if path is None:
        if not tool_slug:
            raise ValueError("tool_slug is required when catalog-entry is not provided")
        path = (catalog_dir or DEFAULT_CATALOG_DIR) / f"{tool_slug}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def _safe_command(command: Any) -> list[str]:
    if not isinstance(command, list) or not command or not all(isinstance(arg, str) for arg in command):
        raise ValueError("canary command must be a non-empty array of strings")
    for arg in command:
        if any(token in arg for token in UNSAFE_ARG_TOKENS):
            raise ValueError(f"unsafe shell token in canary command argument: {arg!r}")
    return command


def _is_version_only(command: list[str]) -> bool:
    if len(command) <= 1:
        return False
    args = {arg.lower() for arg in command[1:]}
    return bool(args) and args.issubset(VERSION_ARGS)


def _render_arg(arg: str, install_root: Path, work_dir: Path) -> str:
    return arg.format(install_root=str(install_root), work_dir=str(work_dir))


def run_canary(
    entry: dict[str, Any],
    *,
    install_root: Path,
    evidence_dir: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    acquisition = entry.get("acquisition") or {}
    canary_type = acquisition.get("canary_type", "not_required")
    tool_slug = entry.get("tool_slug", "unknown-tool")
    steps = acquisition.get("canary_steps") or []
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_dir / f"{tool_slug}-canary-{uuid.uuid4()}.json"

    report: dict[str, Any] = {
        "ok": False,
        "tool_slug": tool_slug,
        "canary_type": canary_type,
        "started_at": now_text(),
        "finished_at": None,
        "evidence_pointer": str(evidence_path),
        "steps": [],
    }

    if canary_type == "not_required":
        report["ok"] = True
        report["finished_at"] = now_text()
        evidence_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    if not steps:
        report["error"] = "acquisition.canary_steps is required for functional/smoke canaries"
        report["finished_at"] = now_text()
        evidence_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    non_version_command_seen = False
    run_env = os.environ.copy()
    run_env.update(env or {})
    bin_dir = install_root / "bin"
    if bin_dir.exists():
        run_env["PATH"] = f"{bin_dir}{os.pathsep}{run_env.get('PATH', '')}"

    for index, step in enumerate(steps, start=1):
        step_type = step.get("type")
        name = step.get("name") or f"step-{index}"
        step_report: dict[str, Any] = {"name": name, "type": step_type, "ok": False}
        try:
            if step_type == "command":
                command = [
                    _render_arg(arg, install_root, evidence_dir)
                    for arg in _safe_command(step.get("command"))
                ]
                if not _is_version_only(command):
                    non_version_command_seen = True
                completed = subprocess.run(
                    command,
                    cwd=str(install_root),
                    env=run_env,
                    timeout=int(step.get("timeout_seconds") or 60),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                step_report.update(
                    {
                        "command": command,
                        "returncode": completed.returncode,
                        "stdout": completed.stdout[-4000:],
                        "stderr": completed.stderr[-4000:],
                        "ok": completed.returncode == 0,
                    }
                )
            elif step_type == "assert_path_exists":
                raw_path = step.get("path")
                if not isinstance(raw_path, str) or not raw_path:
                    raise ValueError("assert_path_exists step requires path")
                path = Path(_render_arg(raw_path, install_root, evidence_dir))
                if not path.is_absolute():
                    path = install_root / path
                step_report.update({"path": str(path), "ok": path.exists()})
            else:
                raise ValueError(f"unsupported canary step type: {step_type!r}")
        except Exception as exc:
            step_report.update({"ok": False, "error": str(exc)})
        report["steps"].append(step_report)
        if not step_report["ok"]:
            report["error"] = f"canary step failed: {name}"
            break

    if "error" not in report and canary_type == "functional" and not non_version_command_seen:
        report["error"] = "functional canary must exercise capability, not only --version"

    report["ok"] = "error" not in report and all(step["ok"] for step in report["steps"])
    report["finished_at"] = now_text()
    evidence_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-entry", help="Path to a tool catalog YAML entry.")
    parser.add_argument("--catalog-dir", default=str(DEFAULT_CATALOG_DIR), help="Catalog directory when using --tool-slug.")
    parser.add_argument("--tool-slug", help="Catalog tool slug when --catalog-entry is omitted.")
    parser.add_argument("--install-root", required=True, help="Project-local install root to run the canary from.")
    parser.add_argument("--evidence-dir", required=True, help="Directory where canary evidence JSON is written.")
    parser.add_argument("--json", action="store_true", help="Emit JSON report to stdout.")
    args = parser.parse_args()

    try:
        entry = load_entry(
            Path(args.catalog_entry).resolve() if args.catalog_entry else None,
            catalog_dir=Path(args.catalog_dir).resolve(),
            tool_slug=args.tool_slug,
        )
        report = run_canary(
            entry,
            install_root=Path(args.install_root).resolve(),
            evidence_dir=Path(args.evidence_dir).resolve(),
        )
    except Exception as exc:
        report = {"ok": False, "error": str(exc), "evidence_pointer": None}

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{'PASS' if report.get('ok') else 'FAIL'}: {report.get('evidence_pointer') or report.get('error')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
