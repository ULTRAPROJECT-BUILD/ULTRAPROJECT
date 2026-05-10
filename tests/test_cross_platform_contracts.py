from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


CORE_RUNTIME_FILES = [
    "scripts/agent_runtime.py",
    "scripts/verify_release.py",
    "scripts/ensure_qc_walkthrough.py",
    "vault/config/platform.md",
]


def read_repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_ci_runs_on_native_windows():
    workflow = yaml.safe_load(read_repo_file(".github/workflows/ci.yml"))
    matrix = workflow["jobs"]["test"]["strategy"]["matrix"]

    assert "windows-latest" in matrix["os"]
    assert "ubuntu-latest" in matrix["os"]


def test_claude_hooks_use_python_entrypoints_not_bash_scripts():
    settings = json.loads(read_repo_file(".claude/settings.json"))
    commands: list[str] = []
    for hook_groups in settings["hooks"].values():
        for hook_group in hook_groups:
            for hook in hook_group["hooks"]:
                commands.append(hook["command"])

    assert commands
    assert all(command.startswith("python .claude/hooks/") for command in commands)
    assert all(not command.endswith(".sh") for command in commands)


def test_core_runtime_has_no_hardcoded_posix_shell_or_homebrew_paths():
    forbidden_patterns = [
        r"/bin/zsh",
        r"/opt/homebrew/bin/(?:codex|gemini)",
        r"subprocess\.(?:run|Popen)\(\s*\[\s*[\"']open[\"']",
    ]

    for path in CORE_RUNTIME_FILES:
        text = read_repo_file(path)
        for pattern in forbidden_patterns:
            assert not re.search(pattern, text), f"{path} contains forbidden pattern {pattern!r}"


def test_core_docs_do_not_present_wsl_as_required_for_windows():
    readme = read_repo_file("README.md")
    setup = read_repo_file("docs/SETUP.md")

    assert "no longer required for the core bootstrap" in readme
    assert "Windows PowerShell example" in setup
    assert "Use native Windows" in setup
