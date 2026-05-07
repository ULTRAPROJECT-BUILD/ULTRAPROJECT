from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "set_agent_mode.py"


def load_set_agent_mode():
    spec = importlib.util.spec_from_file_location("set_agent_mode_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_write_agent_mode_inserts_and_updates_mode_line(tmp_path):
    set_agent_mode = load_set_agent_mode()
    platform_path = tmp_path / "platform.md"
    platform_path.write_text(
        "\n".join(
            [
                "## Agent Routing",
                "",
                "```yaml",
                "agent_routing:",
                "  agents:",
                "    claude:",
                '      cli: "claude -p"',
                "      enabled: true",
                "    codex:",
                '      cli: "codex exec"',
                "      enabled: true",
                "  task_routing:",
                "    general: claude",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # When agent_mode line is absent, default is the system default (chat_native).
    assert set_agent_mode.read_agent_mode(platform_path) == "chat_native"

    set_agent_mode.write_agent_mode(platform_path, "codex_fallback")
    text = platform_path.read_text(encoding="utf-8")

    assert "  agent_mode: codex_fallback\n" in text
    assert set_agent_mode.read_agent_mode(platform_path) == "codex_fallback"

    set_agent_mode.write_agent_mode(platform_path, "normal")
    assert set_agent_mode.read_agent_mode(platform_path) == "normal"

    set_agent_mode.write_agent_mode(platform_path, "chat_native")
    assert set_agent_mode.read_agent_mode(platform_path) == "chat_native"


def test_read_agent_mode_ignores_inline_comments(tmp_path):
    set_agent_mode = load_set_agent_mode()
    platform_path = tmp_path / "platform.md"
    platform_path.write_text(
        "\n".join(
            [
                "## Agent Routing",
                "",
                "```yaml",
                "agent_routing:",
                "  agent_mode: codex_fallback  # temporary degraded mode",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert set_agent_mode.read_agent_mode(platform_path) == "codex_fallback"
