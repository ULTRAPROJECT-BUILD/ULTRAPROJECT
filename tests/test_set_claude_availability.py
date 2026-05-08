from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "set_claude_availability.py"


def load_set_claude_availability():
    spec = importlib.util.spec_from_file_location("set_claude_availability_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_read_and_write_claude_enabled(tmp_path):
    module = load_set_claude_availability()
    platform_path = tmp_path / "platform.md"
    platform_path.write_text(
        "\n".join(
            [
                "## Agent Routing",
                "",
                "```yaml",
                "agent_routing:",
                "  agent_mode: normal",
                "  agents:",
                "    claude:",
                '      cli: "claude -p"',
                "      enabled: true",
                "    codex:",
                '      cli: "codex exec"',
                "      enabled: true",
                "  task_routing:",
                "    orchestration: claude",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert module.read_claude_enabled(platform_path) is True

    module.write_claude_enabled(platform_path, False)
    assert module.read_claude_enabled(platform_path) is False
    assert "      enabled: false\n" in platform_path.read_text(encoding="utf-8")

    module.write_claude_enabled(platform_path, True)
    assert module.read_claude_enabled(platform_path) is True

