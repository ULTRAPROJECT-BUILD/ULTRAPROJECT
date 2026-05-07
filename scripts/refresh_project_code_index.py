#!/usr/bin/env python3
from __future__ import annotations

"""
Refresh project-scoped GitNexus code intelligence for discovered code workspaces.

This script reads a project's artifact index, finds any code workspaces, and runs
GitNexus indexing only when the relevant repo HEAD changed. Dependency workspaces
are skipped by default so the orchestrator does not mutate upstream repos unless
explicitly asked to.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_project_context import default_index_path

REPO_ROOT = SCRIPT_DIR.parent
STATE_PATH = REPO_ROOT / "data" / "project_code_index_state.json"
BOOTSTRAP_MARKER_FILES = (
    "package.json",
    "pnpm-workspace.yaml",
    "turbo.json",
    "tsconfig.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
)
BOOTSTRAP_EXCLUDE_PATHS = (
    "node_modules",
    ".turbo",
    "dist",
    "coverage",
    "test-results",
    "playwright-report",
    ".next",
    ".cache",
    "tmp",
    "temp",
    "build",
)
BOOTSTRAP_COMMIT_MESSAGE = "chore: bootstrap workspace"
BOOTSTRAP_AUTHOR_NAME = "Agent Platform"
BOOTSTRAP_AUTHOR_EMAIL = "agent-platform@local"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", help="Artifact index manifest path.")
    parser.add_argument("--project-file", help="Project markdown path; artifact index path will be derived automatically.")
    parser.add_argument("--force", action="store_true", help="Refresh even if the repo HEAD is unchanged.")
    parser.add_argument(
        "--include-dependencies",
        action="store_true",
        help="Also refresh dependency workspaces (default: primary/supporting workspaces only).",
    )
    args = parser.parse_args()
    if bool(args.manifest) == bool(args.project_file):
        parser.error("Provide exactly one of --manifest or --project-file.")
    return args


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    return data if isinstance(data, dict) else {}


def load_state() -> dict[str, Any]:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"workspaces": {}}
    if not isinstance(data, dict):
        return {"workspaces": {}}
    workspaces = data.get("workspaces")
    if not isinstance(workspaces, dict):
        data["workspaces"] = {}
    return data


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S %Z %z")


def run_command(
    command: list[str],
    cwd: Path,
    *,
    timeout: int = 30,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except Exception as exc:
        return 1, "", str(exc)
    return result.returncode, (result.stdout or "").strip(), (result.stderr or "").strip()


def git_info(root: Path) -> dict[str, Any]:
    branch_rc, branch_out, _ = run_command(["git", "branch", "--show-current"], root)
    head_rc, head_out, _ = run_command(["git", "rev-parse", "HEAD"], root)
    dirty_rc, dirty_out, _ = run_command(["git", "status", "--porcelain"], root)
    return {
        "branch": branch_out if branch_rc == 0 else "",
        "head": head_out if head_rc == 0 else "",
        "dirty": bool(dirty_out) if dirty_rc == 0 else False,
    }


def workspace_has_bootstrap_markers(root: Path) -> bool:
    return any((root / marker).exists() for marker in BOOTSTRAP_MARKER_FILES)


def should_bootstrap_workspace(workspace: dict[str, Any], root: Path, *, include_dependencies: bool) -> bool:
    if not workspace.get("exists") or workspace.get("git_repo"):
        return False
    if workspace.get("role") == "dependency" and not include_dependencies:
        return False
    if not bool(workspace.get("gitnexus_enabled")):
        return False
    return workspace_has_bootstrap_markers(root)


def bootstrap_git_workspace(root: Path) -> tuple[bool, str]:
    init_rc, _, init_err = run_command(["git", "init", "-b", "main"], root)
    if init_rc != 0:
        fallback_rc, _, fallback_err = run_command(["git", "init"], root)
        if fallback_rc != 0:
            return False, init_err or fallback_err or "git init failed"

    author_env = os.environ.copy()
    author_env.update(
        {
            "GIT_AUTHOR_NAME": BOOTSTRAP_AUTHOR_NAME,
            "GIT_AUTHOR_EMAIL": BOOTSTRAP_AUTHOR_EMAIL,
            "GIT_COMMITTER_NAME": BOOTSTRAP_AUTHOR_NAME,
            "GIT_COMMITTER_EMAIL": BOOTSTRAP_AUTHOR_EMAIL,
        }
    )
    pathspecs = ["."] + [f":(exclude){entry}" for entry in BOOTSTRAP_EXCLUDE_PATHS]
    add_rc, _, add_err = run_command(["git", "add", "--all", "--", *pathspecs], root, env=author_env)
    if add_rc != 0:
        add_rc, _, add_err = run_command(["git", "add", "-A"], root, env=author_env)
        if add_rc != 0:
            return False, add_err or "git add failed"

    status_rc, status_out, status_err = run_command(["git", "status", "--porcelain"], root, env=author_env)
    if status_rc != 0:
        return False, status_err or "git status failed"

    commit_command = ["git", "commit", "-m", BOOTSTRAP_COMMIT_MESSAGE]
    if not status_out:
        commit_command.insert(2, "--allow-empty")
    commit_rc, _, commit_err = run_command(commit_command, root, timeout=120, env=author_env)
    if commit_rc != 0:
        return False, commit_err or "git commit failed"
    return True, ""


def gitnexus_command() -> list[str]:
    if shutil.which("pnpm"):
        return ["pnpm", "dlx", "gitnexus@latest"]
    return ["npx", "-y", "gitnexus@latest"]


def run_gitnexus_analyze(root: Path) -> tuple[int, str, str]:
    return run_command(gitnexus_command() + ["analyze", "--skip-agents-md"], root, timeout=1800)


def workspace_entry_key(workspace: dict[str, Any]) -> str:
    return str(workspace.get("key") or workspace.get("root") or "").strip()


def should_refresh_workspace(workspace: dict[str, Any], *, include_dependencies: bool) -> bool:
    if not workspace.get("exists") or not workspace.get("git_repo"):
        return False
    if workspace.get("role") == "dependency" and not include_dependencies:
        return False
    return bool(workspace.get("gitnexus_enabled"))


def refresh_project_code_index(
    manifest_path: Path,
    *,
    force: bool = False,
    include_dependencies: bool = False,
) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve()
    manifest = load_yaml(manifest_path)
    project = str(manifest.get("project") or "").strip()
    client = str(manifest.get("client") or "").strip()
    workspaces = manifest.get("code_workspaces") or []
    if not isinstance(workspaces, list):
        workspaces = []

    state = load_state()
    state_workspaces = state.setdefault("workspaces", {})
    refreshed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for workspace in workspaces:
        if not isinstance(workspace, dict):
            continue
        key = workspace_entry_key(workspace)
        root = Path(str(workspace.get("root") or "")).expanduser()
        if should_bootstrap_workspace(workspace, root, include_dependencies=include_dependencies):
            boot_ok, boot_error = bootstrap_git_workspace(root)
            if not boot_ok:
                skipped.append(
                    {
                        "root": str(root),
                        "reason": "bootstrap_failed",
                        "role": workspace.get("role", ""),
                        "error": boot_error[-200:],
                    }
                )
                continue
            workspace = {**workspace, "git_repo": True}
        if not should_refresh_workspace(workspace, include_dependencies=include_dependencies):
            reason = "workspace_missing"
            if workspace.get("role") == "dependency" and not include_dependencies:
                reason = "dependency_skipped"
            elif workspace.get("exists") and workspace.get("git_repo") and not workspace.get("gitnexus_enabled"):
                reason = "disabled"
            elif workspace.get("exists") and not workspace.get("git_repo"):
                reason = "not_bootstrappable"
            skipped.append({"root": str(root), "reason": reason, "role": workspace.get("role", "")})
            continue

        info = git_info(root)
        previous = state_workspaces.get(key, {}) if isinstance(state_workspaces, dict) else {}
        previous = previous if isinstance(previous, dict) else {}
        if not force and previous.get("head") == info.get("head") and previous.get("last_status") == "refreshed":
            skipped.append({"root": str(root), "reason": "unchanged", "role": workspace.get("role", "")})
            continue

        returncode, stdout, stderr = run_gitnexus_analyze(root)
        status = "refreshed" if returncode == 0 else "failed"
        entry = {
            "project": project,
            "client": client,
            "root": str(root),
            "role": workspace.get("role", ""),
            "launcher": " ".join(gitnexus_command()[:2]),
            "branch": info.get("branch", ""),
            "head": info.get("head", ""),
            "dirty": bool(info.get("dirty")),
            "updated_at": now(),
            "last_status": status,
            "gitnexus_index_present": (root / ".gitnexus").exists(),
            "last_stdout": stdout[-2000:],
            "last_stderr": stderr[-2000:],
        }
        state_workspaces[key] = entry
        refreshed.append({"root": str(root), "status": status, "role": workspace.get("role", ""), "head": info.get("head", "")})

    save_state(state)
    if refreshed:
        status = "refreshed" if all(item["status"] == "refreshed" for item in refreshed) else "partial"
    else:
        status = "noop"
    return {
        "status": status,
        "project": project,
        "client": client,
        "manifest": str(manifest_path),
        "refreshed": refreshed,
        "skipped": skipped,
        "workspace_count": len(workspaces),
    }


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else default_index_path(Path(args.project_file).expanduser().resolve())
    result = refresh_project_code_index(
        manifest_path,
        force=args.force,
        include_dependencies=args.include_dependencies,
    )
    if result["status"] == "refreshed":
        print(f"Refreshed GitNexus for {len(result['refreshed'])} workspace(s).")
    elif result["status"] == "partial":
        print(f"GitNexus refresh partially completed for {len(result['refreshed'])} workspace(s).")
    else:
        reasons = ", ".join(item["reason"] for item in result.get("skipped", [])[:3]) or "no_code_workspaces"
        print(f"Skipped GitNexus refresh for {result.get('project') or 'project'} ({reasons}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
