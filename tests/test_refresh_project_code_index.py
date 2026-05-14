from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "refresh_project_code_index.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_manifest(path: Path, *, workspaces: list[dict] | None = None) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "project": "sample-project",
                "client": "acme",
                "generated_at": "2026-04-13T13:00:00 EDT -0400",
                "code_workspaces": workspaces or [],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    subprocess.run(["git", "add", "package.json"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_gitnexus_command_prefers_pnpm_when_available(monkeypatch):
    module = load_module("refresh_project_code_index_command_pnpm_under_test", SCRIPT_PATH)

    monkeypatch.setattr(module.shutil, "which", lambda name: "/opt/homebrew/bin/pnpm" if name == "pnpm" else None)

    assert module.gitnexus_command() == ["pnpm", "dlx", "gitnexus@latest"]


def test_gitnexus_command_falls_back_to_npx_when_pnpm_missing(monkeypatch):
    module = load_module("refresh_project_code_index_command_npx_under_test", SCRIPT_PATH)

    monkeypatch.setattr(module.shutil, "which", lambda _name: None)

    assert module.gitnexus_command() == ["npx", "-y", "gitnexus@latest"]


def test_refresh_project_code_index_noops_without_workspace(tmp_path):
    module = load_module("refresh_project_code_index_noop_under_test", SCRIPT_PATH)
    manifest_path = tmp_path / "sample-project.artifact-index.yaml"
    write_manifest(manifest_path, workspaces=[])
    module.STATE_PATH = tmp_path / "project_code_index_state.json"

    result = module.refresh_project_code_index(manifest_path)

    assert result["status"] == "noop"
    assert result["workspace_count"] == 0


def test_refresh_project_code_index_skips_dependency_workspace_by_default(tmp_path, monkeypatch):
    module = load_module("refresh_project_code_index_dependency_under_test", SCRIPT_PATH)
    repo = tmp_path / "framework"
    init_repo(repo)
    manifest_path = tmp_path / "sample-project.artifact-index.yaml"
    write_manifest(
        manifest_path,
        workspaces=[
            {
                "root": str(repo),
                "key": str(repo),
                "role": "dependency",
                "exists": True,
                "git_repo": True,
                "gitnexus_enabled": True,
            }
        ],
    )
    module.STATE_PATH = tmp_path / "project_code_index_state.json"

    called = {"value": False}

    def fake_analyze(_root: Path):
        called["value"] = True
        return 0, "ok", ""

    monkeypatch.setattr(module, "run_gitnexus_analyze", fake_analyze)
    result = module.refresh_project_code_index(manifest_path)

    assert result["status"] == "noop"
    assert result["skipped"][0]["reason"] == "dependency_skipped"
    assert called["value"] is False


def test_refresh_project_code_index_runs_when_primary_repo_head_changes(tmp_path, monkeypatch):
    module = load_module("refresh_project_code_index_refresh_under_test", SCRIPT_PATH)
    repo = tmp_path / "app"
    init_repo(repo)
    manifest_path = tmp_path / "sample-project.artifact-index.yaml"
    write_manifest(
        manifest_path,
        workspaces=[
            {
                "root": str(repo),
                "key": str(repo),
                "role": "primary",
                "exists": True,
                "git_repo": True,
                "gitnexus_enabled": True,
            }
        ],
    )
    module.STATE_PATH = tmp_path / "project_code_index_state.json"

    monkeypatch.setattr(module, "run_gitnexus_analyze", lambda _root: (0, "indexed", ""))
    result = module.refresh_project_code_index(manifest_path)

    assert result["status"] == "refreshed"
    saved = json.loads(module.STATE_PATH.read_text(encoding="utf-8"))
    workspace_state = next(iter(saved["workspaces"].values()))
    assert workspace_state["last_status"] == "refreshed"
    assert workspace_state["root"] == str(repo)
    assert workspace_state["launcher"] in {"pnpm dlx", "npx -y"}


def test_refresh_project_code_index_bootstraps_primary_scaffold_into_git_repo(tmp_path, monkeypatch):
    module = load_module("refresh_project_code_index_bootstrap_under_test", SCRIPT_PATH)
    repo = tmp_path / "app"
    repo.mkdir(parents=True, exist_ok=True)
    (repo / ".gitignore").write_text("node_modules\n", encoding="utf-8")
    (repo / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    (repo / "tsconfig.json").write_text('{"compilerOptions":{}}\n', encoding="utf-8")
    manifest_path = tmp_path / "sample-project.artifact-index.yaml"
    write_manifest(
        manifest_path,
        workspaces=[
            {
                "root": str(repo),
                "key": str(repo),
                "role": "primary",
                "exists": True,
                "git_repo": False,
                "gitnexus_enabled": True,
            }
        ],
    )
    module.STATE_PATH = tmp_path / "project_code_index_state.json"

    def fake_analyze(root: Path):
        assert (root / ".git").exists()
        return 0, "indexed", ""

    monkeypatch.setattr(module, "run_gitnexus_analyze", fake_analyze)
    result = module.refresh_project_code_index(manifest_path)

    assert result["status"] == "refreshed"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    saved = json.loads(module.STATE_PATH.read_text(encoding="utf-8"))
    workspace_state = next(iter(saved["workspaces"].values()))
    assert workspace_state["last_status"] == "refreshed"
    assert workspace_state["head"]


def test_refresh_project_code_index_noops_when_head_unchanged(tmp_path, monkeypatch):
    module = load_module("refresh_project_code_index_unchanged_under_test", SCRIPT_PATH)
    repo = tmp_path / "app"
    init_repo(repo)
    manifest_path = tmp_path / "sample-project.artifact-index.yaml"
    write_manifest(
        manifest_path,
        workspaces=[
            {
                "root": str(repo),
                "key": str(repo),
                "role": "primary",
                "exists": True,
                "git_repo": True,
                "gitnexus_enabled": True,
            }
        ],
    )
    module.STATE_PATH = tmp_path / "project_code_index_state.json"
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    module.save_state({"workspaces": {str(repo): {"head": head, "last_status": "refreshed"}}})

    called = {"value": False}

    def fake_analyze(_root: Path):
        called["value"] = True
        return 0, "indexed", ""

    monkeypatch.setattr(module, "run_gitnexus_analyze", fake_analyze)
    result = module.refresh_project_code_index(manifest_path)

    assert result["status"] == "noop"
    assert result["skipped"][0]["reason"] == "unchanged"
    assert called["value"] is False
