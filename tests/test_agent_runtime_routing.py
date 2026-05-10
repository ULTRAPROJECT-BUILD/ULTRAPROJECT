from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "agent_runtime.py"


def load_agent_runtime():
    spec = importlib.util.spec_from_file_location("agent_runtime_routing_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def clone_routing(routing: dict) -> dict:
    return json.loads(json.dumps(routing))


class DummyProcess:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.pid = 43210
        self.returncode = 0

    def poll(self):
        return self.returncode


def write_ticket(
    path: Path,
    *,
    ticket_id: str = "T-001",
    task_type: str | None = "code_build",
    status: str = "open",
    project: str = "demo-project",
    phase: int | None = None,
    wave: str | None = None,
    blocked_by: str = "[]",
    created: str = "2026-04-08T21:00",
    updated: str = "2026-04-08T21:00",
    completed: str | None = None,
    extra_frontmatter: dict[str, object] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "type: ticket",
        f"id: {ticket_id}",
        'title: "Example ticket"',
        f"status: {status}",
    ]
    if task_type is not None:
        lines.append(f"task_type: {task_type}")
    lines.extend(
        [
            f'project: "{project}"',
            f"created: {created}",
            f"updated: {updated}",
            f"blocked_by: {blocked_by}",
        ]
    )
    if completed is not None:
        lines.append(f"completed: {completed}")
    if phase is not None:
        lines.append(f"phase: {phase}")
    if wave is not None:
        lines.append(f'wave: "{wave}"')
    if extra_frontmatter:
        for key, value in extra_frontmatter.items():
            rendered = json.dumps(value) if isinstance(value, str) and (":" in value or " " in value) else str(value).lower() if isinstance(value, bool) else str(value)
            lines.append(f"{key}: {rendered}")
    lines.extend(
        [
            "---",
            "",
            "# Example ticket",
            "",
            "## Work Log",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_brief_snapshot(
    path: Path,
    *,
    project: str,
    title: str,
    captured: str,
    brief_scope: str | None = None,
    phase: int | None = None,
    ticket: str | None = None,
    covered_waves: str | None = None,
) -> None:
    lines = [
        "---",
        "type: snapshot",
        "subtype: creative-brief",
        f'title: "{title}"',
        f'project: "{project}"',
    ]
    if brief_scope is not None:
        lines.append(f"brief_scope: {brief_scope}")
    if phase is not None:
        lines.append(f"phase: {phase}")
    if ticket is not None:
        lines.append(f"ticket: {ticket}")
    if covered_waves is not None:
        lines.append(f"covered_waves: {covered_waves}")
    lines.extend([f"captured: {captured}", f"updated: {captured}", "---", "", f"# {title}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_brief_review(
    path: Path,
    *,
    project: str,
    title: str,
    updated: str,
    phase: int | None = None,
    ticket: str | None = None,
    grade: str = "A",
    advance_allowed: str = "yes",
    body_lines: list[str] | None = None,
) -> None:
    lines = [
        "---",
        "type: snapshot",
        "subtype: brief-review",
        f'title: "{title}"',
        f'project: "{project}"',
        f'grade: "{grade}"',
        f'advance_allowed: "{advance_allowed}"',
    ]
    if phase is not None:
        lines.append(f"phase: {phase}")
    if ticket is not None:
        lines.append(f"ticket: {ticket}")
    lines.extend([f"updated: {updated}", "---", "", f"# {title}", ""])
    if body_lines:
        lines.extend(body_lines)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def run_task_args(
    tmp_path: Path,
    *,
    task_type: str | None = "general",
    force_agent: str | None = None,
    ticket_path: Path | None = None,
) -> argparse.Namespace:
    platform_path = tmp_path / "config" / "platform.md"
    platform_path.parent.mkdir(parents=True, exist_ok=True)
    platform_path.write_text("", encoding="utf-8")
    metering_path = tmp_path / "metering.md"
    return argparse.Namespace(
        platform=platform_path,
        metering=metering_path,
        task_type=task_type,
        project="demo-project",
        client="demo-client",
        cwd=str(tmp_path),
        prompt="Review and fix the task.",
        prompt_file=None,
        force_agent=force_agent,
        ticket_tags=None,
        ticket_path=str(ticket_path) if ticket_path else None,
    )


def spawn_task_args(
    tmp_path: Path,
    *,
    task_type: str | None = "code_build",
    force_agent: str | None = None,
    ticket_path: Path | None = None,
) -> argparse.Namespace:
    platform_path = tmp_path / "config" / "platform.md"
    platform_path.parent.mkdir(parents=True, exist_ok=True)
    platform_path.write_text("", encoding="utf-8")
    metering_path = tmp_path / "metering.md"
    return argparse.Namespace(
        platform=platform_path,
        metering=metering_path,
        task_type=task_type,
        project="demo-project",
        client="demo-client",
        cwd=str(tmp_path),
        prompt="Resume the deep ticket.",
        prompt_file=None,
        force_agent=force_agent,
        ticket_tags=None,
        ticket_path=str(ticket_path) if ticket_path else None,
    )


def test_load_agent_routing_reads_agent_mode(tmp_path):
    agent_runtime = load_agent_runtime()
    platform_path = tmp_path / "platform.md"
    platform_path.write_text(
        "\n".join(
            [
                "## Agent Routing",
                "",
                "```yaml",
                "agent_routing:",
                "  agent_mode: codex_fallback",
                "  agents:",
                "    claude:",
                '      cli: "claude -p"',
                "      enabled: true",
                "      monthly_credit_budget: 100",
                "      priority: 1",
                "    codex:",
                '      cli: "codex exec"',
                "      enabled: true",
                "      monthly_credit_budget: 100",
                "      priority: 2",
                "  task_routing:",
                "    general: claude",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    routing = agent_runtime.load_agent_routing(platform_path)

    assert routing["agent_mode"] == "codex_fallback"


def test_choose_agent_routes_all_tasks_to_codex_in_fallback_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "codex_fallback"
    routing["agents"]["codex"]["enabled"] = True

    choice = agent_runtime.choose_agent(routing, [], "self_review")

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"
    assert choice["agent_mode"] == "codex_fallback"
    assert "codex_fallback mode is active" in choice["reason"]


def test_choose_agent_falls_back_when_codex_fallback_requested_but_codex_disabled():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "codex_fallback"
    routing["agents"]["codex"]["enabled"] = False
    routing["agents"]["claude"]["enabled"] = True

    choice = agent_runtime.choose_agent(routing, [], "code_build")

    assert choice["agent"] == "claude"
    assert choice["preferred"] == "codex"
    assert "codex is disabled" in choice["reason"]


def test_chat_native_routes_to_claude_when_claudecode_env_set(monkeypatch):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "chat_native"
    routing["host_agent"] = ""
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = False

    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_HOME", raising=False)

    choice = agent_runtime.choose_agent(routing, [], "code_review")

    assert choice["agent"] == "claude"
    assert choice["preferred"] == "claude"
    assert choice["agent_mode"] == "chat_native"
    assert "chat_native mode" in choice["reason"]
    assert "CLAUDECODE" in choice["reason"]


def test_chat_native_explicit_host_agent_overrides_env(monkeypatch):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "chat_native"
    routing["host_agent"] = "codex"
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = True

    # Even though CLAUDECODE is set, explicit host_agent: codex wins.
    monkeypatch.setenv("CLAUDECODE", "1")

    choice = agent_runtime.choose_agent(routing, [], "code_review")

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"
    assert "host_agent: codex set in platform.md" in choice["reason"]


def test_chat_native_defaults_to_claude_with_warning_when_no_signal(monkeypatch):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "chat_native"
    routing["host_agent"] = ""
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = False

    for env_var, _ in agent_runtime.HOST_AGENT_ENV_FINGERPRINTS:
        monkeypatch.delenv(env_var, raising=False)

    choice = agent_runtime.choose_agent(routing, [], "code_review")

    assert choice["agent"] == "claude"
    assert "no host signal" in choice["reason"]
    assert "set host_agent: codex in platform.md" in choice["reason"]


def test_chat_native_overrides_force_agent_codex_when_host_is_claude(monkeypatch, tmp_path):
    """When chat_native resolves to claude, --force-agent codex on a gate
    should be redirected to claude (same as claude_fallback behaviour)."""
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "chat_native"
    routing["host_agent"] = ""
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = True

    monkeypatch.setenv("CLAUDECODE", "1")

    args = argparse.Namespace(force_agent="codex")

    decision = agent_runtime.resolve_agent_choice_for_task(
        args=args,
        routing=routing,
        entries=[],
        task_type="code_review",
        ticket_context={},
        ticket_tags=[],
    )

    assert decision["agent"] == "claude"
    assert decision["preferred"] == "claude"
    assert "chat_native" in decision["reason"]


def test_force_agent_role_gate_reviewer_resolves_to_host_in_chat_native(monkeypatch):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "chat_native"
    routing["host_agent"] = ""
    monkeypatch.setenv("CLAUDECODE", "1")

    resolved, reason = agent_runtime.resolve_force_agent_role("gate_reviewer", routing)

    assert resolved == "claude"
    assert "role=gate_reviewer resolved via chat_native" in reason
    assert "CLAUDECODE" in reason


def test_force_agent_role_gate_reviewer_resolves_to_codex_in_normal(monkeypatch):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    monkeypatch.setenv("CLAUDECODE", "1")  # ignored in normal mode

    resolved, reason = agent_runtime.resolve_force_agent_role("gate_reviewer", routing)

    assert resolved == "codex"
    assert "role=gate_reviewer resolved via normal mode" in reason
    assert "task_routing[code_review] = codex" in reason


def test_force_agent_role_visual_reviewer_resolves_to_claude_in_normal(monkeypatch):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"

    resolved, reason = agent_runtime.resolve_force_agent_role("visual_reviewer", routing)

    assert resolved == "claude"
    assert "role=visual_reviewer resolved via normal mode" in reason
    assert "task_routing[visual_review] = claude" in reason


def test_force_agent_role_resolves_via_fallback_target(monkeypatch):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)

    routing["agent_mode"] = "claude_fallback"
    resolved, reason = agent_runtime.resolve_force_agent_role("gate_reviewer", routing)
    assert resolved == "claude"
    assert "claude_fallback" in reason

    routing["agent_mode"] = "codex_fallback"
    resolved, reason = agent_runtime.resolve_force_agent_role("visual_reviewer", routing)
    assert resolved == "codex"
    assert "codex_fallback" in reason


def test_force_agent_role_unknown_raises():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)

    try:
        agent_runtime.resolve_force_agent_role("nonexistent_role", routing)
    except ValueError as e:
        assert "Unknown --force-agent role" in str(e)
    else:
        raise AssertionError("Expected ValueError for unknown role")


def test_resolve_agent_choice_substitutes_gate_reviewer_role(monkeypatch):
    """End-to-end: --force-agent gate_reviewer in chat_native should resolve
    to the host agent (claude here) before the existing routing logic runs."""
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "chat_native"
    routing["host_agent"] = ""
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = False
    monkeypatch.setenv("CLAUDECODE", "1")

    args = argparse.Namespace(force_agent="gate_reviewer")

    decision = agent_runtime.resolve_agent_choice_for_task(
        args=args,
        routing=routing,
        entries=[],
        task_type="code_review",
        ticket_context={},
        ticket_tags=[],
    )

    assert decision["agent"] == "claude"
    # The role should have been substituted on args before existing logic ran.
    assert args.force_agent == "claude"


def test_resolve_agent_choice_substitutes_visual_reviewer_in_normal(monkeypatch):
    """In normal mode, visual_reviewer should resolve to whatever
    task_routing[visual_review] says (claude by default)."""
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = True

    args = argparse.Namespace(force_agent="visual_reviewer")

    decision = agent_runtime.resolve_agent_choice_for_task(
        args=args,
        routing=routing,
        entries=[],
        task_type="visual_review",
        ticket_context={},
        ticket_tags=[],
    )

    assert decision["agent"] == "claude"
    assert args.force_agent == "claude"


def test_load_agent_routing_reads_host_agent(tmp_path):
    agent_runtime = load_agent_runtime()
    platform_path = tmp_path / "platform.md"
    platform_path.write_text(
        "\n".join(
            [
                "# Platform",
                "",
                "## Agent Routing",
                "",
                "```yaml",
                "agent_routing:",
                "  agent_mode: chat_native",
                "  host_agent: codex",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    routing = agent_runtime.load_agent_routing(platform_path)

    assert routing["agent_mode"] == "chat_native"
    assert routing["host_agent"] == "codex"


def test_choose_agent_routes_worker_reviews_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    choice = agent_runtime.choose_agent(routing, [], "self_review")

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"


def test_choose_agent_keeps_ui_worker_review_on_codex_even_with_ui_tags():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    choice = agent_runtime.choose_agent(routing, [], "quality_check", ticket_tags=["ui-design"])

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"
    assert "preferred routed agent for quality_check" in choice["reason"]


def test_choose_agent_ignores_stitch_tag_for_non_visual_creative_brief():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    choice = agent_runtime.choose_agent(
        routing,
        [],
        "creative_brief",
        ticket_tags=["creative-brief", "stitch-required"],
        ticket_context={"task_type": "creative_brief", "ui_work": False, "stitch_required": False, "design_mode": ""},
    )

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"


def test_choose_agent_keeps_visual_creative_brief_on_codex_despite_stitch_tags():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    choice = agent_runtime.choose_agent(
        routing,
        [],
        "creative_brief",
        ticket_tags=["creative-brief", "stitch-required"],
        ticket_context={"task_type": "creative_brief", "ui_work": True, "stitch_required": True, "design_mode": "stitch_required"},
    )

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"


def test_choose_agent_routes_general_tasks_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["gemini"]["enabled"] = False

    choice = agent_runtime.choose_agent(routing, [], "general")

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"


def test_choose_agent_routes_standard_code_review_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["gemini"]["enabled"] = True

    choice = agent_runtime.choose_agent(routing, [], "code_review")

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"


def test_choose_agent_routes_briefs_manifests_and_artifact_polish_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    for task_type in (
        "creative_brief",
        "verification_manifest_generate",
        "verification_manifest_execute",
        "test_manifest_generate",
        "test_manifest_execute",
        "artifact_polish_review",
        "vault_navigation",
    ):
        choice = agent_runtime.choose_agent(routing, [], task_type)

        assert choice["agent"] == "codex"
        assert choice["preferred"] == "codex"


def test_choose_agent_routes_adversarial_probe_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["gemini"]["enabled"] = True

    choice = agent_runtime.choose_agent(routing, [], "adversarial_probe")

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"


def test_run_task_attempt_launches_child_in_new_session(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    captured: dict[str, object] = {}

    class StubProcess:
        pid = 54321
        returncode = 0

        def poll(self):
            return self.returncode

    def fake_popen(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return StubProcess()

    monkeypatch.setattr(agent_runtime.subprocess, "Popen", fake_popen)

    attempt = agent_runtime.run_task_attempt(
        agent_name="codex",
        choice={"preferred": "codex"},
        routing=clone_routing(agent_runtime.DEFAULT_ROUTING),
        prompt="Check the lane.",
        cwd=str(tmp_path),
        ticket_path=None,
        ledger_path=None,
        task_type="code_build",
        project="demo-project",
        client="demo-client",
    )

    assert attempt["returncode"] == 0
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["close_fds"] is True


def test_command_spawn_task_detaches_runtime_wrapper(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type="code_build", blocked_by="[]")
    args = spawn_task_args(tmp_path, ticket_path=ticket_path)
    captured: dict[str, object] = {}

    class StubProcess:
        pid = 60001

    def fake_popen(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return StubProcess()

    monkeypatch.setattr(agent_runtime, "read_prompt", lambda _: "Resume the deep ticket.")
    monkeypatch.setattr(agent_runtime.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        agent_runtime,
        "wait_for_executor_spawn",
        lambda ledger_path, runtime_pid, timeout_secs=5, poll_secs=0.1: {
            "runtime_pid": runtime_pid,
            "child_pid": 60002,
            "status": "running",
        },
    )

    exit_code = agent_runtime.command_spawn_task(args)
    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert exit_code == 0
    assert captured["kwargs"]["stdin"] is subprocess.DEVNULL
    assert captured["kwargs"]["start_new_session"] is True
    assert captured["kwargs"]["close_fds"] is True
    command = captured["args"][0]
    assert Path(command[0]).name in {"python", "python3", "python.exe"}
    assert "run-task" in command
    assert "--ticket-path" in command
    assert payload["runtime_pid"] == 60001
    assert payload["child_pid"] == 60002
    assert payload["status"] == "running"


def test_command_spawn_task_waits_for_stitch_auth_before_launch(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-657-stitch.md"
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="code_build",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )
    args = spawn_task_args(tmp_path, ticket_path=ticket_path)

    monkeypatch.setattr(agent_runtime, "read_prompt", lambda _: "Use Stitch MCP for the UI.")
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda _: {})
    monkeypatch.setattr(
        agent_runtime,
        "ensure_stitch_ticket_ready",
        lambda ticket_path, design_context, target_agent=None: {
            "status": "auth_required",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?fake=1",
            "snapshot_path": str(tmp_path / "stitch-auth.md"),
        },
    )

    def fail_popen(*args, **kwargs):
        raise AssertionError("spawn-task should not launch the runtime when Stitch auth is missing")

    monkeypatch.setattr(agent_runtime.subprocess, "Popen", fail_popen)

    exit_code = agent_runtime.command_spawn_task(args)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "waiting_for_stitch_auth"
    assert payload["runtime_pid"] is None
    assert payload["auth_url"].startswith("https://accounts.google.com/")


def test_command_spawn_task_waits_for_stitch_api_key_before_launch(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-657-stitch.md"
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="code_build",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )
    args = spawn_task_args(tmp_path, ticket_path=ticket_path)

    monkeypatch.setattr(agent_runtime, "read_prompt", lambda _: "Use Stitch MCP for the UI.")
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda _: {})
    monkeypatch.setattr(
        agent_runtime,
        "ensure_stitch_ticket_ready",
        lambda ticket_path, design_context, target_agent=None: {
            "status": "api_key_required",
            "snapshot_path": str(tmp_path / "stitch-api-key.md"),
        },
    )

    def fail_popen(*args, **kwargs):
        raise AssertionError("spawn-task should not launch the runtime when Stitch API key is missing")

    monkeypatch.setattr(agent_runtime.subprocess, "Popen", fail_popen)

    exit_code = agent_runtime.command_spawn_task(args)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "waiting_for_stitch_api_key"
    assert payload["runtime_pid"] is None
    assert payload["auth_snapshot_path"].endswith("stitch-api-key.md")


def test_ensure_stitch_ticket_ready_marks_ticket_waiting_and_writes_snapshot(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    fake_repo = tmp_path / "repo"
    ticket_path = fake_repo / "vault" / "clients" / "demo-client" / "tickets" / "T-657-stitch.md"
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="code_build",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )
    monkeypatch.setattr(agent_runtime, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(agent_runtime, "STITCH_AUTH_STATE_PATH", fake_repo / "vault" / "config" / "stitch-auth-state.json")
    monkeypatch.setattr(agent_runtime, "STITCH_CLAUDE_CWD", fake_repo / "vault")
    monkeypatch.setattr(
        agent_runtime,
        "get_stitch_mcp_status",
        lambda: {"status": "needs_auth", "detail": "Needs authentication"},
    )
    monkeypatch.setattr(
        agent_runtime,
        "request_stitch_auth_flow",
        lambda: {
            "status": "pending",
            "session_id": "session-123",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?fake=1",
            "requested_at": "2026-04-13T15:00",
        },
    )

    result = agent_runtime.ensure_stitch_ticket_ready(ticket_path, {"requires_stitch": True}, target_agent="claude")
    ticket_data = agent_runtime.parse_frontmatter_map(ticket_path)
    snapshot_path = Path(result["snapshot_path"])

    assert result["status"] == "auth_required"
    assert ticket_data["status"] == "waiting"
    assert "STITCH-AUTH" in str(ticket_data["blocked_by"])
    assert snapshot_path.exists()
    assert "https://accounts.google.com/o/oauth2/v2/auth?fake=1" in snapshot_path.read_text(encoding="utf-8")


def test_get_stitch_mcp_status_reports_api_key_missing_for_local_proxy(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir(parents=True, exist_ok=True)
    (fake_repo / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "stitch": {
                        "type": "stdio",
                        "command": "node",
                        "args": [str(fake_repo / "tools" / "stitch-mcp-proxy" / "server.mjs")],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(agent_runtime, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(agent_runtime, "STITCH_PROXY_SERVER_RELATIVE", Path("tools/stitch-mcp-proxy/server.mjs"))
    monkeypatch.delenv("STITCH_API_KEY", raising=False)

    called = {"value": False}

    def unexpected_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("Claude should not be called when the API key is missing locally.")

    monkeypatch.setattr(agent_runtime, "run_claude_capture", unexpected_run)

    status = agent_runtime.get_stitch_mcp_status()

    assert status["status"] == "api_key_missing"
    assert "STITCH_API_KEY" in status["detail"]
    assert called["value"] is False


def test_ensure_stitch_ticket_ready_passes_for_claude_target_when_registry_connected(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-657-stitch.md"
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="code_build",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )
    monkeypatch.setattr(
        agent_runtime,
        "get_stitch_mcp_status",
        lambda: {"status": "connected", "detail": "Status: Connected"},
    )

    result = agent_runtime.ensure_stitch_ticket_ready(ticket_path, {"requires_stitch": True}, target_agent="claude")

    assert result["status"] == "ready"
    assert result["target_agent"] == "claude"


def test_ensure_stitch_ticket_ready_fails_for_codex_target_when_codex_config_absent(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-657-stitch.md"
    codex_config = tmp_path / "config.toml"
    codex_config.write_text(
        "\n".join(
            [
                'model = "gpt-5.4"',
                "",
                "[mcp_servers.nexus]",
                'command = "node"',
                'args = ["/tmp/nexus.js"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="quality_check",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )
    monkeypatch.setattr(agent_runtime, "CODEX_CONFIG_PATH", codex_config)
    monkeypatch.setattr(
        agent_runtime,
        "get_stitch_mcp_status",
        lambda: {"status": "connected", "detail": "Status: Connected"},
    )

    result = agent_runtime.ensure_stitch_ticket_ready(ticket_path, {"requires_stitch": True}, target_agent="codex")

    assert result["status"] == "codex_config_missing"
    assert result["target_agent"] == "codex"
    assert "[mcp_servers.stitch]" in result["detail"]


def test_ensure_stitch_ticket_ready_passes_for_codex_target_when_both_registries_ready(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-657-stitch.md"
    codex_config = tmp_path / "config.toml"
    codex_config.write_text(
        "\n".join(
            [
                'model = "gpt-5.4"',
                "",
                "[mcp_servers.stitch]",
                'command = "node"',
                'args = ["/path/to/platform/tools/stitch-mcp-proxy/server.mjs"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="quality_check",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )
    monkeypatch.setattr(agent_runtime, "CODEX_CONFIG_PATH", codex_config)
    monkeypatch.setattr(
        agent_runtime,
        "get_stitch_mcp_status",
        lambda: {"status": "connected", "detail": "Status: Connected"},
    )

    result = agent_runtime.ensure_stitch_ticket_ready(ticket_path, {"requires_stitch": True}, target_agent="codex")

    assert result["status"] == "ready"
    assert result["target_agent"] == "codex"


def test_ensure_stitch_ticket_ready_blocks_codex_code_build_without_sealed_package(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-774-stitch-build.md"
    write_ticket(
        ticket_path,
        ticket_id="T-774",
        task_type="code_build",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )

    def fail_live_stitch_check():
        raise AssertionError("Codex code_build should require a sealed package before live Stitch checks")

    monkeypatch.setattr(agent_runtime, "get_stitch_mcp_status", fail_live_stitch_check)

    result = agent_runtime.ensure_stitch_ticket_ready(
        ticket_path,
        {
            "requires_stitch": True,
            "codex_code_build_requires_sealed_stitch_package": True,
        },
        target_agent="codex",
    )
    ticket_data = agent_runtime.parse_frontmatter_map(ticket_path)

    assert result["status"] == "stitch_design_package_required"
    assert result["blocker"] == "STITCH-DESIGN-PACKAGE"
    assert ticket_data["status"] == "blocked"
    assert "STITCH-DESIGN-PACKAGE" in str(ticket_data["blocked_by"])
    assert "Runtime Stitch package guard blocked Codex implementation" in ticket_path.read_text(encoding="utf-8")


def test_ensure_stitch_ticket_ready_allows_codex_code_build_with_sealed_package(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    package_dir = tmp_path / "sealed-stitch-package"
    package_dir.mkdir()
    (package_dir / "manifest.json").write_text('{"screens":[]}\n', encoding="utf-8")
    ticket_path = tmp_path / "T-774-stitch-build.md"
    write_ticket(
        ticket_path,
        ticket_id="T-774",
        task_type="code_build",
        blocked_by="[STITCH-DESIGN-PACKAGE]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
            "stitch_design_package_ref": str(package_dir),
        },
    )

    def fail_live_stitch_check():
        raise AssertionError("Sealed-package Codex code_build should not call live Stitch MCP")

    monkeypatch.setattr(agent_runtime, "get_stitch_mcp_status", fail_live_stitch_check)

    result = agent_runtime.ensure_stitch_ticket_ready(
        ticket_path,
        {
            "requires_stitch": True,
            "codex_code_build_requires_sealed_stitch_package": True,
        },
        target_agent="codex",
    )
    ticket_data = agent_runtime.parse_frontmatter_map(ticket_path)

    assert result["status"] == "ready"
    assert result["implementation_from_sealed_stitch_package"] is True
    assert result["sealed_design_package_ref"] == str(package_dir)
    assert result["sealed_design_package_path"] == str(package_dir.resolve())
    assert ticket_data["status"] == "open"
    assert "STITCH-DESIGN-PACKAGE" not in str(ticket_data["blocked_by"])


def test_command_spawn_task_blocks_codex_stitch_code_build_without_design_package(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-774-stitch-build.md"
    write_ticket(
        ticket_path,
        ticket_id="T-774",
        task_type="code_build",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )
    args = spawn_task_args(tmp_path, ticket_path=ticket_path)

    monkeypatch.setattr(agent_runtime, "read_prompt", lambda _: "Implement the Stitch-required UI.")
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    # This test exercises cross-model routing (code_build → codex per the
    # task_routing table). chat_native would route everything to the host
    # CLI, bypassing the table — pin to normal mode explicitly.
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda _platform: routing)
    contract = dict(agent_runtime.DEFAULT_QUALITY_CONTRACT)
    contract["stitch_required_codex_code_build_requires_sealed_design_package"] = True
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda _platform: contract)

    def fail_popen(*args, **kwargs):
        raise AssertionError("spawn-task should not launch Codex without a sealed Stitch package")

    monkeypatch.setattr(agent_runtime.subprocess, "Popen", fail_popen)

    exit_code = agent_runtime.command_spawn_task(args)
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["status"] == "stitch_design_package_required"
    assert payload["runtime_pid"] is None
    assert payload["blocker"] == "STITCH-DESIGN-PACKAGE"


def test_runtime_preamble_for_sealed_stitch_package_does_not_require_live_mcp():
    agent_runtime = load_agent_runtime()

    preamble = agent_runtime.build_runtime_preamble(
        "2026-04-19T00:00 EDT -0400",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        design_context={
            "ui_work": True,
            "design_mode": "stitch_required",
            "requires_stitch": True,
            "reason": "Test sealed-package implementation.",
            "implementation_from_sealed_stitch_package": True,
            "sealed_design_package_ref": "/tmp/sealed-package",
            "sealed_design_package_path": "/tmp/sealed-package",
        },
        ticket_context={"task_type": "code_build", "title": "Build sealed Stitch UI"},
    )

    assert "sealed Stitch/design package" in preamble
    assert "Do not call live Stitch MCP" in preamble
    assert "Use Stitch MCP via the stitch-design skill" not in preamble
    assert "If Stitch MCP is unavailable" not in preamble


def test_ensure_stitch_ticket_ready_marks_ticket_waiting_for_api_key(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    fake_repo = tmp_path / "repo"
    ticket_path = fake_repo / "vault" / "clients" / "demo-client" / "tickets" / "T-657-stitch.md"
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="code_build",
        blocked_by="[]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )

    monkeypatch.setattr(agent_runtime, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(agent_runtime, "STITCH_AUTH_STATE_PATH", fake_repo / "vault" / "config" / "stitch-auth-state.json")
    monkeypatch.setattr(
        agent_runtime,
        "get_stitch_mcp_status",
        lambda: {"status": "api_key_missing", "detail": "Project-local Stitch MCP proxy is configured, but STITCH_API_KEY is missing."},
    )

    result = agent_runtime.ensure_stitch_ticket_ready(ticket_path, {"requires_stitch": True}, target_agent="claude")
    ticket_data = agent_runtime.parse_frontmatter_map(ticket_path)
    snapshot_path = Path(result["snapshot_path"])
    snapshot_text = snapshot_path.read_text(encoding="utf-8")

    assert result["status"] == "api_key_required"
    assert ticket_data["status"] == "waiting"
    assert "STITCH-API-KEY" in str(ticket_data["blocked_by"])
    assert "STITCH-AUTH" not in str(ticket_data["blocked_by"])
    assert snapshot_path.exists()
    assert "STITCH_API_KEY=" in snapshot_text
    assert ".env" in snapshot_text


def test_complete_stitch_auth_reopens_waiting_tickets_when_connected(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    fake_repo = tmp_path / "repo"
    state_path = fake_repo / "vault" / "config" / "stitch-auth-state.json"
    ticket_path = fake_repo / "vault" / "clients" / "demo-client" / "tickets" / "T-657-stitch.md"
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="code_build",
        status="waiting",
        blocked_by="[STITCH-AUTH]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )

    monkeypatch.setattr(agent_runtime, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(agent_runtime, "STITCH_AUTH_STATE_PATH", state_path)
    monkeypatch.setattr(agent_runtime, "STITCH_CLAUDE_CWD", fake_repo / "vault")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    agent_runtime.write_json_map(
        state_path,
        {
            "status": "pending",
            "session_id": "session-123",
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?fake=1",
            "requested_at": "2026-04-13T15:00",
        },
    )

    monkeypatch.setattr(
        agent_runtime,
        "run_claude_capture",
        lambda command, timeout_secs=30: subprocess.CompletedProcess(command, 0, stdout="Authentication complete", stderr=""),
    )
    monkeypatch.setattr(
        agent_runtime,
        "get_stitch_mcp_status",
        lambda: {"status": "connected", "detail": "Status: Connected"},
    )

    result = agent_runtime.complete_stitch_auth("http://localhost:53261/callback?state=fresh&code=abc")
    reopened = agent_runtime.reopen_waiting_stitch_tickets()
    ticket_data = agent_runtime.parse_frontmatter_map(ticket_path)

    assert result["status"] == "connected"
    assert reopened == ["T-657"]
    assert ticket_data["status"] == "open"
    assert "STITCH-AUTH" not in str(ticket_data.get("blocked_by", ""))


def test_ensure_stitch_ticket_ready_reopens_api_key_blocker_when_connected(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    fake_repo = tmp_path / "repo"
    ticket_path = fake_repo / "vault" / "clients" / "demo-client" / "tickets" / "T-657-stitch.md"
    write_ticket(
        ticket_path,
        ticket_id="T-657",
        task_type="code_build",
        status="waiting",
        blocked_by="[STITCH-API-KEY]",
        extra_frontmatter={
            "ui_work": True,
            "design_mode": "stitch_required",
            "stitch_required": True,
        },
    )

    monkeypatch.setattr(agent_runtime, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(
        agent_runtime,
        "get_stitch_mcp_status",
        lambda: {"status": "connected", "detail": "Status: Connected"},
    )

    result = agent_runtime.ensure_stitch_ticket_ready(ticket_path, {"requires_stitch": True}, target_agent="claude")
    ticket_data = agent_runtime.parse_frontmatter_map(ticket_path)

    assert result["status"] == "ready"
    assert result["reopened"] is True
    assert ticket_data["status"] == "open"
    assert "STITCH-API-KEY" not in str(ticket_data.get("blocked_by", ""))


def test_resolve_runtime_arg_path_falls_back_to_repo_root_when_cwd_changes(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    fake_repo_root = tmp_path / "repo"
    platform_path = fake_repo_root / "vault" / "config" / "platform.md"
    platform_path.parent.mkdir(parents=True, exist_ok=True)
    platform_path.write_text("", encoding="utf-8")
    (fake_repo_root / "vault").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(agent_runtime, "REPO_ROOT", fake_repo_root)
    monkeypatch.chdir(fake_repo_root / "vault")

    resolved = agent_runtime.resolve_runtime_arg_path(Path("vault/config/platform.md"))

    assert resolved == platform_path.resolve()


def test_build_run_task_subprocess_command_uses_repo_root_config_paths(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    fake_repo_root = tmp_path / "repo"
    platform_path = fake_repo_root / "vault" / "config" / "platform.md"
    metering_path = fake_repo_root / "vault" / "config" / "metering.md"
    platform_path.parent.mkdir(parents=True, exist_ok=True)
    platform_path.write_text("", encoding="utf-8")
    metering_path.write_text("", encoding="utf-8")
    (fake_repo_root / "vault").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(agent_runtime, "REPO_ROOT", fake_repo_root)
    monkeypatch.chdir(fake_repo_root / "vault")

    args = argparse.Namespace(
        platform=Path("vault/config/platform.md"),
        metering=Path("vault/config/metering.md"),
        task_type="code_build",
        project="demo-project",
        client="demo-client",
        force_agent=None,
        ticket_tags=None,
        ticket_path=str(fake_repo_root / "vault" / "tickets" / "T-001-example.md"),
    )

    command = agent_runtime.build_run_task_subprocess_command(
        args,
        cwd=str(fake_repo_root / "vault"),
        prompt_file="/tmp/demo.prompt.txt",
    )

    assert command[4] == str(platform_path.resolve())
    assert command[6] == str(metering_path.resolve())


def test_choose_agent_keeps_orchestration_on_claude_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    choice = agent_runtime.choose_agent(routing, [], "orchestration")

    assert choice["agent"] == "claude"
    assert choice["preferred"] == "claude"


def test_choose_agent_routes_project_reconciliation_task_types_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    for task_type in (
        "project_change_control",
        "project_amendment",
        "project_replan",
        "plan_rebase",
        "plan_rebaseline",
        "plan_reconciliation",
        "roadmap_reconciliation",
        "architecture_decision",
    ):
        choice = agent_runtime.choose_agent(routing, [], task_type)

        assert choice["agent"] == "codex"
        assert choice["preferred"] == "codex"
        assert f"codex is the preferred routed agent for {task_type}" in choice["reason"]


def test_choose_agent_routes_scope_update_orchestration_ticket_to_codex():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    choice = agent_runtime.choose_agent(
        routing,
        [],
        "orchestration",
        ticket_tags=["project-change-control", "scope-update", "project-replan"],
        ticket_context={
            "task_type": "orchestration",
            "title": "Apply admin scope update to Project #051",
        },
    )

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"
    assert "project amendment/reconciliation routing" in choice["reason"]


def test_choose_agent_keeps_strategy_judgment_orchestration_on_claude():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True

    choice = agent_runtime.choose_agent(
        routing,
        [],
        "orchestration",
        ticket_tags=["strategy-review", "project-change-control"],
        ticket_context={
            "task_type": "orchestration",
            "title": "Admin strategy review for project operating model",
        },
    )

    assert choice["agent"] == "claude"
    assert choice["preferred"] == "claude"


def test_choose_agent_keeps_planner_and_design_on_claude_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = True

    planner_choice = agent_runtime.choose_agent(routing, [], "planner")
    design_choice = agent_runtime.choose_agent(routing, [], "design")
    orchestrator_choice = agent_runtime.choose_agent(routing, [], "orchestrator")

    assert planner_choice["agent"] == "claude"
    assert planner_choice["preferred"] == "claude"
    assert design_choice["agent"] == "claude"
    assert design_choice["preferred"] == "claude"
    assert orchestrator_choice["agent"] == "claude"
    assert orchestrator_choice["preferred"] == "claude"


def test_choose_agent_routes_mechanical_audits_and_rehearsal_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = True

    drift_choice = agent_runtime.choose_agent(routing, [], "drift_detection")
    rehearsal_choice = agent_runtime.choose_agent(routing, [], "simulation_rehearsal")

    assert drift_choice["agent"] == "codex"
    assert drift_choice["preferred"] == "codex"
    assert rehearsal_choice["agent"] == "codex"
    assert rehearsal_choice["preferred"] == "codex"


def test_choose_agent_routes_artifact_cleanup_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["gemini"]["enabled"] = False

    choice = agent_runtime.choose_agent(routing, [], "artifact_cleanup")

    assert choice["agent"] == "codex"
    assert choice["preferred"] == "codex"
    assert "codex is the preferred routed agent for artifact_cleanup" in choice["reason"]


def test_choose_agent_routes_receipt_and_docs_cleanup_to_codex_when_gemini_disabled():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["gemini"]["enabled"] = False

    receipt_choice = agent_runtime.choose_agent(routing, [], "receipt_cleanup")
    docs_choice = agent_runtime.choose_agent(routing, [], "docs_cleanup")

    assert receipt_choice["agent"] == "codex"
    assert receipt_choice["preferred"] == "codex"
    assert "codex is the preferred routed agent for receipt_cleanup" in receipt_choice["reason"]
    assert docs_choice["agent"] == "codex"
    assert docs_choice["preferred"] == "codex"
    assert "codex is the preferred routed agent for docs_cleanup" in docs_choice["reason"]


def test_choose_agent_routes_remediation_task_types_to_codex_in_normal_mode():
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agent_mode"] = "normal"
    routing["agents"]["claude"]["enabled"] = True
    routing["agents"]["codex"]["enabled"] = True

    for task_type in ("brief_remediation", "evidence_cleanup", "gate_remediation"):
        choice = agent_runtime.choose_agent(routing, [], task_type)

        assert choice["agent"] == "codex"
        assert choice["preferred"] == "codex"
        assert f"codex is the preferred routed agent for {task_type}" in choice["reason"]


def test_cli_ticket_tags_ignored_when_ticket_path_provided(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    # Pin to normal (cross-model) so code_build routes per the task_routing
    # table; chat_native would route everything to the detected host CLI.
    routing["agent_mode"] = "normal"
    routing["agents"]["codex"]["enabled"] = True
    routing["agents"]["claude"]["enabled"] = True
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type="code_build")

    args = argparse.Namespace(
        platform=tmp_path / "config" / "platform.md",
        metering=tmp_path / "metering.md",
        task_type="general",
        ticket_tags=["multimodal-required"],
        ticket_path=str(ticket_path),
        format="json",
    )

    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: routing)

    returncode = agent_runtime.command_choose_agent(args)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert returncode == 0
    assert payload["agent"] == "codex"
    assert payload["preferred"] == "codex"
    assert payload["ticket_tags"] == []


def test_build_command_constructs_gemini_flags():
    agent_runtime = load_agent_runtime()

    command = agent_runtime.build_command("gemini", "/opt/homebrew/bin/gemini", "Normalize the receipt wording.", "/tmp/demo")

    assert command[:3] == ["/opt/homebrew/bin/gemini", "-p", "Normalize the receipt wording."]
    assert "--approval-mode" in command
    assert "yolo" in command
    assert "--output-format" in command
    assert "stream-json" in command


def test_build_command_constructs_claude_stream_json_flags():
    agent_runtime = load_agent_runtime()

    command = agent_runtime.build_command("claude", "claude -p", "Capture the QC proof.", "/tmp/demo")

    assert command[:3] == ["claude", "-p", "Capture the QC proof."]
    assert "--output-format" in command
    assert "stream-json" in command
    assert "--dangerously-skip-permissions" in command


def test_default_claude_runtime_cli_pins_opus_47_max_effort():
    agent_runtime = load_agent_runtime()

    assert (
        agent_runtime.DEFAULT_ROUTING["agents"]["claude"]["cli"]
        == "claude -p --model claude-opus-4-7 --effort max"
    )


def test_parse_token_usage_reads_stream_json_usage():
    agent_runtime = load_agent_runtime()

    output = "\n".join(
        [
            '{"type":"stream_event","event":{"type":"message_start","message":{"usage":{"input_tokens":1,"output_tokens":2}}}}',
            '{"type":"assistant","message":{"usage":{"input_tokens":321,"output_tokens":123}}}',
        ]
    )

    assert agent_runtime.parse_token_usage(output) == (321, 123)


def test_build_runtime_preamble_uses_nexus_for_discovery_and_direct_reads_for_exact_files():
    agent_runtime = load_agent_runtime()

    preamble = agent_runtime.build_runtime_preamble("2026-04-05T15:00 EDT -0400", {})

    assert "prefer project-scoped hybrid retrieval first" in preamble
    assert "Nexus MCP as an accelerator" in preamble
    assert "prefer project-scoped hybrid retrieval first" in preamble
    assert "semantic text search over the curated project corpus" in preamble
    assert "Once you know the exact target files, read them directly." in preamble


def test_build_runtime_preamble_adds_deep_execution_reporting_contract():
    agent_runtime = load_agent_runtime()

    preamble = agent_runtime.build_runtime_preamble(
        "2026-04-05T15:00 EDT -0400",
        {},
        ticket_context={"complexity": "deep"},
    )

    assert "Deep execution reporting contract for this task" in preamble
    assert "PLAN — Decomposed into N sub-steps" in preamble
    assert "Reuse those exact step labels" in preamble


def test_determine_hybrid_retrieval_context_requires_targeted_pass_for_deep_qc():
    agent_runtime = load_agent_runtime()

    hybrid_context = agent_runtime.determine_hybrid_retrieval_context(
        "quality_check",
        "Review the proof pack, screenshots, and remediation evidence for the current phase gate.",
        {"title": "QC remediation follow-up", "complexity": "deep"},
    )

    assert hybrid_context["required"] is True
    assert hybrid_context["clean_room"] is False
    assert hybrid_context["query_count"] == 3
    assert "deep" in hybrid_context["reason"].lower()


def test_determine_hybrid_retrieval_context_preserves_clean_room_stress_test():
    agent_runtime = load_agent_runtime()

    hybrid_context = agent_runtime.determine_hybrid_retrieval_context(
        "stress_test",
        "Run a clean-room adversarial stress test against the product.",
        {"title": "Stress test execution", "complexity": "deep"},
    )

    assert hybrid_context["required"] is False
    assert hybrid_context["clean_room"] is True
    assert "clean-room" in hybrid_context["reason"].lower()


def test_determine_hybrid_retrieval_context_preserves_clean_room_adversarial_probe():
    agent_runtime = load_agent_runtime()

    hybrid_context = agent_runtime.determine_hybrid_retrieval_context(
        "adversarial_probe",
        "Run a clean-room adversarial probe against the new permission and write paths.",
        {"title": "Phase adversarial probe", "complexity": "deep"},
    )

    assert hybrid_context["required"] is False
    assert hybrid_context["clean_room"] is True
    assert "clean-room" in hybrid_context["reason"].lower()


def test_build_runtime_preamble_adds_hybrid_retrieval_escalation_block():
    agent_runtime = load_agent_runtime()

    preamble = agent_runtime.build_runtime_preamble(
        "2026-04-14T14:00 EDT -0400",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        ticket_context={"title": "QC remediation follow-up", "complexity": "deep"},
        hybrid_retrieval_context={
            "required": True,
            "clean_room": False,
            "query_count": 3,
            "reason": "Ticket complexity is `deep` and the task spans multiple artifacts.",
        },
    )

    assert "Hybrid retrieval escalation for this task" in preamble
    assert "run 3 targeted project-scoped hybrid retrieval queries" in preamble
    assert "short retrieval digest" in preamble


def test_determine_nexus_context_marks_vault_navigation_as_optional_nexus_help():
    agent_runtime = load_agent_runtime()

    nexus_context = agent_runtime.determine_nexus_context("vault_navigation", "Trace related docs.", {})

    assert nexus_context["nexus_first"] is False
    assert nexus_context["nexus_optional"] is True
    assert "discovery-heavy" in nexus_context["reason"]


def test_determine_nexus_context_marks_general_vault_lookup_as_optional_nexus_help():
    agent_runtime = load_agent_runtime()

    nexus_context = agent_runtime.determine_nexus_context("general", "Use backlinks to find related tickets and proofs in the vault.", {})

    assert nexus_context["nexus_first"] is False
    assert nexus_context["nexus_optional"] is True
    assert "project-scoped retrieval first" in nexus_context["reason"]


def test_determine_nexus_context_leaves_plain_general_code_work_alone():
    agent_runtime = load_agent_runtime()

    nexus_context = agent_runtime.determine_nexus_context("general", "Fix the failing Python unit test in runtime helpers.", {})

    assert nexus_context["nexus_first"] is False
    assert nexus_context["nexus_optional"] is False


def test_build_runtime_preamble_adds_optional_nexus_advisory_when_requested():
    agent_runtime = load_agent_runtime()

    preamble = agent_runtime.build_runtime_preamble(
        "2026-04-05T15:00 EDT -0400",
        {},
        nexus_context={"nexus_first": False, "nexus_optional": True, "reason": "Task type `vault_navigation` is discovery-heavy, so project-scoped retrieval should lead and Nexus can help only if a curated vault is already open."},
    )

    assert "Optional Nexus assist for this task" in preamble
    assert "Do not block on Nexus availability" in preamble


def test_explicit_concept_required_internal_ui_does_not_auto_escalate_to_stitch():
    agent_runtime = load_agent_runtime()

    design_context = agent_runtime.determine_design_context(
        "code_build",
        "Build the approval workflow UI for the governance dashboard with plan queue, evidence tabs, and approve/reject flow.",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        {
            "title": "Approval workflow UI — proof review",
            "ui_work": True,
            "design_mode": "concept_required",
            "stitch_required": False,
            "public_surface": False,
            "existing_surface_redesign": False,
            "page_contract_required": True,
        },
        ["ui-design", "approval-ui"],
    )

    assert design_context["ui_work"] is True
    assert design_context["design_mode"] == "concept_required"
    assert design_context["requires_stitch"] is False


def test_implicit_high_complexity_ui_defaults_to_concept_not_stitch():
    agent_runtime = load_agent_runtime()

    design_context = agent_runtime.determine_design_context(
        "code_build",
        "Build a multi-step admin panel dashboard settings flow with several screen states.",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        {
            "title": "Admin panel redesign",
            "ui_work": True,
        },
        ["ui-design"],
    )

    assert design_context["design_mode"] == "concept_required"
    assert design_context["requires_stitch"] is False


def test_existing_public_surface_redesign_preserves_explicit_concept_mode():
    agent_runtime = load_agent_runtime()

    design_context = agent_runtime.determine_design_context(
        "code_build",
        "Redesign the existing homepage hero and marketing site navigation.",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        {
            "title": "Homepage redesign",
            "ui_work": True,
            "design_mode": "concept_required",
            "public_surface": True,
            "existing_surface_redesign": True,
        },
        ["ui-design", "existing-surface-redesign"],
    )

    assert design_context["design_mode"] == "concept_required"
    assert design_context["requires_stitch"] is False


def test_existing_internal_route_family_redesign_preserves_concept_mode():
    agent_runtime = load_agent_runtime()

    design_context = agent_runtime.determine_design_context(
        "code_build",
        "Redesign the existing pending review route for the operator console so it matches the approved route family.",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        {
            "title": "Pending Review route redesign",
            "ui_work": True,
            "design_mode": "concept_required",
            "public_surface": False,
            "existing_surface_redesign": True,
            "route_family_required": True,
        },
        ["ui-design", "route-family-required"],
    )

    assert design_context["design_mode"] == "concept_required"
    assert design_context["requires_stitch"] is False
    assert design_context["route_family_required"] is True


def test_build_runtime_preamble_adds_route_family_requirements():
    agent_runtime = load_agent_runtime()

    preamble = agent_runtime.build_runtime_preamble(
        "2026-04-13T23:30 EDT -0400",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        design_context={
            "ui_work": True,
            "design_mode": "stitch_required",
            "reason": "Existing route-family surface redesign.",
            "public_surface": False,
            "page_contract_required": False,
            "route_family_required": True,
            "existing_surface_redesign": True,
        },
        ticket_context={"task_type": "quality_check"},
    )

    assert "Route Family section" in preamble
    assert "same-product-family parity" in preamble


def test_build_runtime_preamble_adds_semantic_screenshot_preservation_policy():
    agent_runtime = load_agent_runtime()

    preamble = agent_runtime.build_runtime_preamble(
        "2026-04-18T10:45 EDT -0400",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        design_context={
            "ui_work": True,
            "design_mode": "stitch_required",
            "reason": "Existing route-family surface redesign.",
            "public_surface": False,
            "page_contract_required": True,
            "route_family_required": True,
            "existing_surface_redesign": True,
        },
        ticket_context={"task_type": "quality_check"},
    )

    assert "hashes prove copy integrity for the same captured artifact" in preamble
    assert "must not be used as byte-identical visual-preservation requirements" in preamble
    assert "semantic preservation gate" in preamble
    assert "Do not copy stale screenshots into a new evidence bundle" in preamble


def test_force_agent_ignored_for_non_gate_task_type_with_ticket_path(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type="code_build")
    args = run_task_args(tmp_path, force_agent="claude", ticket_path=ticket_path)

    routed_task_types: list[str] = []
    built_agents: list[str] = []

    def fake_choose_agent(routing_arg, entries, task_type, ticket_tags=None, ticket_context=None):
        routed_task_types.append(task_type)
        return {
            "agent": "codex" if task_type == "code_build" else "claude",
            "preferred": "codex" if task_type == "code_build" else "claude",
            "reason": f"Routed by task_type={task_type}.",
            "pool": {},
            "agent_mode": "normal",
        }

    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: routing)
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})
    monkeypatch.setattr(agent_runtime, "choose_agent", fake_choose_agent)
    monkeypatch.setattr(agent_runtime, "build_command", lambda agent, cli, prompt, cwd: built_agents.append(agent) or ["fake-agent"])
    monkeypatch.setattr(agent_runtime, "executor_ledger_dir", lambda: tmp_path / "data" / "executors")
    monkeypatch.setattr(agent_runtime.subprocess, "Popen", DummyProcess)

    returncode = agent_runtime.command_run_task(args)
    captured = capsys.readouterr()

    assert returncode == 0
    assert routed_task_types == ["code_build"]
    assert built_agents == ["codex"]
    assert (
        "RUNTIME-ROUTING: Ignoring --force-agent claude for task_type=code_build ticket=T-001. "
        "Automatic routing is enforced unless task_type is one of code_review, credibility_gate, visual_review."
    ) in captured.err


def test_codex_sandbox_failure_retries_with_claude(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type="code_build")
    args = run_task_args(tmp_path, force_agent="claude", ticket_path=ticket_path)

    routed_task_types: list[str] = []
    attempted_agents: list[str] = []
    work_log_notes: list[str] = []
    ledger_payload: dict = {}

    def fake_choose_agent(routing_arg, entries, task_type, ticket_tags=None, ticket_context=None):
        routed_task_types.append(task_type)
        return {
            "agent": "codex",
            "preferred": "codex",
            "reason": f"Routed by task_type={task_type}.",
            "pool": {},
            "agent_mode": "normal",
        }

    def fake_run_task_attempt(**kwargs):
        attempted_agents.append(kwargs["agent_name"])
        if kwargs["agent_name"] == "codex":
            return {
                "agent": "codex",
                "choice": kwargs["choice"],
                "returncode": 1,
                "stdout_text": "",
                "stderr_text": "Operation not permitted inside sandbox",
                "cleanup_action": "",
                "termination_reason": "sandbox_retryable_failure",
            }
        return {
            "agent": "claude",
            "choice": kwargs["choice"],
            "returncode": 0,
            "stdout_text": "claude ok\n",
            "stderr_text": "",
            "cleanup_action": "",
            "termination_reason": "exited_cleanly",
        }

    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: routing)
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})
    monkeypatch.setattr(agent_runtime, "choose_agent", fake_choose_agent)
    monkeypatch.setattr(agent_runtime, "run_task_attempt", fake_run_task_attempt)
    monkeypatch.setattr(agent_runtime, "executor_ledger_dir", lambda: tmp_path / "data" / "executors")
    monkeypatch.setattr(agent_runtime, "write_metering", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_runtime, "append_ticket_work_log", lambda path, note: work_log_notes.append(note))
    monkeypatch.setattr(agent_runtime, "read_executor_ledger", lambda path: dict(ledger_payload))
    monkeypatch.setattr(agent_runtime, "write_executor_ledger", lambda path, payload: ledger_payload.update(payload))
    monkeypatch.setattr(agent_runtime, "finalize_ticket_after_executor", lambda *args, **kwargs: None)

    returncode = agent_runtime.command_run_task(args)
    captured = capsys.readouterr()

    assert returncode == 0
    assert routed_task_types == ["code_build"]
    assert attempted_agents == ["codex", "claude"]
    assert (
        "RUNTIME-ROUTING: Ignoring --force-agent claude for task_type=code_build ticket=T-001. "
        "Automatic routing is enforced unless task_type is one of code_review, credibility_gate, visual_review."
    ) in captured.err
    assert (
        "RUNTIME-RETRY: Codex sandbox failure detected for T-001. "
        "Automatically retrying with Claude."
    ) in captured.err
    assert any(
        "RUNTIME-RETRY: Codex sandbox failure detected for T-001." in note
        for note in work_log_notes
    )


def test_codex_sandbox_failure_skips_claude_retry_when_claude_disabled(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    routing["agents"]["claude"]["enabled"] = False
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type="code_build")
    args = run_task_args(tmp_path, force_agent="claude", ticket_path=ticket_path)

    attempted_agents: list[str] = []
    work_log_notes: list[str] = []
    ledger_payload: dict = {}

    def fake_choose_agent(routing_arg, entries, task_type, ticket_tags=None, ticket_context=None):
        return {
            "agent": "codex",
            "preferred": "codex",
            "reason": f"Routed by task_type={task_type}.",
            "pool": {},
            "agent_mode": "normal",
        }

    def fake_run_task_attempt(**kwargs):
        attempted_agents.append(kwargs["agent_name"])
        return {
            "agent": "codex",
            "choice": kwargs["choice"],
            "returncode": 1,
            "stdout_text": "",
            "stderr_text": "Operation not permitted inside sandbox",
            "cleanup_action": "",
            "termination_reason": "sandbox_retryable_failure",
        }

    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: routing)
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})
    monkeypatch.setattr(agent_runtime, "choose_agent", fake_choose_agent)
    monkeypatch.setattr(agent_runtime, "run_task_attempt", fake_run_task_attempt)
    monkeypatch.setattr(agent_runtime, "executor_ledger_dir", lambda: tmp_path / "data" / "executors")
    monkeypatch.setattr(agent_runtime, "write_metering", lambda *args, **kwargs: None)
    monkeypatch.setattr(agent_runtime, "append_ticket_work_log", lambda path, note: work_log_notes.append(note))
    monkeypatch.setattr(agent_runtime, "read_executor_ledger", lambda path: dict(ledger_payload))
    monkeypatch.setattr(agent_runtime, "write_executor_ledger", lambda path, payload: ledger_payload.update(payload))
    monkeypatch.setattr(agent_runtime, "finalize_ticket_after_executor", lambda *args, **kwargs: None)

    returncode = agent_runtime.command_run_task(args)
    captured = capsys.readouterr()

    assert returncode != 0
    assert attempted_agents == ["codex"]
    assert "Automatically retrying with Claude." not in captured.err
    assert "Claude retry skipped because Claude is disabled." in captured.err
    assert any("Claude retry skipped because Claude is disabled." in note for note in work_log_notes)


def test_force_agent_ignored_for_non_gate_task_type_without_ticket_path(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    args = run_task_args(tmp_path, force_agent="claude", ticket_path=None)

    routed_task_types: list[str] = []
    built_agents: list[str] = []

    def fake_choose_agent(routing_arg, entries, task_type, ticket_tags=None, ticket_context=None):
        routed_task_types.append(task_type)
        return {
            "agent": "codex",
            "preferred": "codex",
            "reason": f"Routed by task_type={task_type}.",
            "pool": {},
            "agent_mode": "normal",
        }

    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: routing)
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})
    monkeypatch.setattr(agent_runtime, "choose_agent", fake_choose_agent)
    monkeypatch.setattr(agent_runtime, "build_command", lambda agent, cli, prompt, cwd: built_agents.append(agent) or ["fake-agent"])
    monkeypatch.setattr(agent_runtime.subprocess, "Popen", DummyProcess)

    returncode = agent_runtime.command_run_task(args)
    captured = capsys.readouterr()

    assert returncode == 0
    assert routed_task_types == ["general"]
    assert built_agents == ["codex"]
    assert (
        "RUNTIME-ROUTING: Ignoring --force-agent claude for task_type=general. "
        "Automatic routing is enforced unless task_type is one of code_review, credibility_gate, visual_review."
    ) in captured.err


def test_force_agent_honored_for_code_review_without_ticket_path(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    args = run_task_args(tmp_path, task_type="code_review", force_agent="claude", ticket_path=None)

    built_agents: list[str] = []

    def fail_choose_agent(*_args, **_kwargs):
        raise AssertionError("choose_agent should not run when force-agent is allowed for gate task types")

    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: routing)
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})
    monkeypatch.setattr(agent_runtime, "choose_agent", fail_choose_agent)
    monkeypatch.setattr(agent_runtime, "build_command", lambda agent, cli, prompt, cwd: built_agents.append(agent) or ["fake-agent"])
    monkeypatch.setattr(agent_runtime.subprocess, "Popen", DummyProcess)

    returncode = agent_runtime.command_run_task(args)
    captured = capsys.readouterr()

    assert returncode == 0
    assert built_agents == ["claude"]
    assert "RUNTIME-ROUTING: Ignoring --force-agent" not in captured.err


def test_force_agent_honored_for_credibility_gate_with_ticket_path(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type="credibility_gate")
    args = run_task_args(tmp_path, task_type="general", force_agent="claude", ticket_path=ticket_path)

    built_agents: list[str] = []

    def fail_choose_agent(*_args, **_kwargs):
        raise AssertionError("choose_agent should not run when ticket task_type is in the force-agent gate set")

    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: routing)
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})
    monkeypatch.setattr(agent_runtime, "choose_agent", fail_choose_agent)
    monkeypatch.setattr(agent_runtime, "build_command", lambda agent, cli, prompt, cwd: built_agents.append(agent) or ["fake-agent"])
    monkeypatch.setattr(agent_runtime, "executor_ledger_dir", lambda: tmp_path / "data" / "executors")
    monkeypatch.setattr(agent_runtime.subprocess, "Popen", DummyProcess)

    returncode = agent_runtime.command_run_task(args)
    captured = capsys.readouterr()

    assert returncode == 0
    assert built_agents == ["claude"]
    assert "RUNTIME-ROUTING: Ignoring --force-agent" not in captured.err


def test_force_agent_honored_for_visual_review_gate_with_ticket_path(tmp_path, monkeypatch, capsys):
    agent_runtime = load_agent_runtime()
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type="visual_review")
    args = run_task_args(tmp_path, task_type="general", force_agent="claude", ticket_path=ticket_path)

    built_agents: list[str] = []

    def fail_choose_agent(*_args, **_kwargs):
        raise AssertionError("choose_agent should not run when ticket task_type is in the force-agent gate set")

    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: routing)
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})
    monkeypatch.setattr(agent_runtime, "choose_agent", fail_choose_agent)
    monkeypatch.setattr(agent_runtime, "build_command", lambda agent, cli, prompt, cwd: built_agents.append(agent) or ["fake-agent"])
    monkeypatch.setattr(agent_runtime, "executor_ledger_dir", lambda: tmp_path / "data" / "executors")
    monkeypatch.setattr(agent_runtime.subprocess, "Popen", DummyProcess)

    returncode = agent_runtime.command_run_task(args)
    captured = capsys.readouterr()

    assert returncode == 0
    assert built_agents == ["claude"]
    assert "RUNTIME-ROUTING: Ignoring --force-agent" not in captured.err


def test_is_sandbox_retryable_failure_matches_only_specific_markers():
    agent_runtime = load_agent_runtime()

    assert agent_runtime.is_sandbox_retryable_failure("Operation not permitted inside sandbox") is True
    assert agent_runtime.is_sandbox_retryable_failure("PermissionError: [Errno 1] blocked") is True
    assert agent_runtime.is_sandbox_retryable_failure("permission denied") is False
    assert agent_runtime.is_sandbox_retryable_failure("sandbox") is False
    assert agent_runtime.is_sandbox_retryable_failure("operation not permitted") is False


def test_effective_task_type_prefers_frontmatter(tmp_path):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type="build")

    ticket_context = agent_runtime.load_ticket_context(str(ticket_path))

    assert agent_runtime.effective_task_type(ticket_context, "creative_brief") == "code_build"


def test_effective_task_type_fallback_to_general():
    agent_runtime = load_agent_runtime()

    assert agent_runtime.effective_task_type({}, None) == "general"


def test_effective_task_type_defaults_to_general_when_ticket_has_no_task_type(tmp_path):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, task_type=None)

    ticket_context = agent_runtime.load_ticket_context(str(ticket_path))

    assert agent_runtime.effective_task_type(ticket_context, "code_review") == "general"


def test_command_run_task_reblocks_ticket_when_governing_wave_brief_has_not_passed_gate(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    tickets_dir = tmp_path / "tickets"
    snapshots_dir = tmp_path / "snapshots"
    brief_ticket = tickets_dir / "T-541-wave-2b-creative-brief.md"
    build_ticket = tickets_dir / "T-542-feedback-memory-run-records.md"

    write_ticket(
        brief_ticket,
        ticket_id="T-541",
        task_type="creative_brief",
        status="closed",
        project="demo-project",
        phase=2,
        wave="2B",
        updated="2026-04-08T23:46",
        completed="2026-04-08T23:45",
    )
    write_ticket(
        build_ticket,
        ticket_id="T-542",
        task_type="code_build",
        status="open",
        project="demo-project",
        phase=2,
        wave="2B",
        blocked_by="[]",
    )
    write_brief_snapshot(
        snapshots_dir / "2026-04-08-creative-brief-wave2b-demo-project.md",
        project="demo-project",
        title="Creative Brief — Wave 2B Supplement",
        captured="2026-04-08T23:45",
        brief_scope="phase",
        phase=2,
        ticket="T-541",
        covered_waves='["Wave 2B"]',
    )

    args = run_task_args(tmp_path, ticket_path=build_ticket)
    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: clone_routing(agent_runtime.DEFAULT_ROUTING))
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})

    with pytest.raises(SystemExit, match=r"RUNTIME-BLOCKED: T-542 cannot start"):
        agent_runtime.command_run_task(args)

    data = agent_runtime.parse_frontmatter_map(build_ticket)
    content = build_ticket.read_text(encoding="utf-8")

    assert data["status"] == "blocked"
    assert "T-541" in data["blocked_by"]
    assert "Runtime dependency guard re-blocked ticket." in content


def test_command_run_task_allows_ticket_when_governing_wave_brief_has_passing_gate(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    tickets_dir = tmp_path / "tickets"
    snapshots_dir = tmp_path / "snapshots"
    brief_ticket = tickets_dir / "T-541-wave-2b-creative-brief.md"
    build_ticket = tickets_dir / "T-542-feedback-memory-run-records.md"

    write_ticket(
        brief_ticket,
        ticket_id="T-541",
        task_type="creative_brief",
        status="closed",
        project="demo-project",
        phase=2,
        wave="2B",
        updated="2026-04-08T23:46",
        completed="2026-04-08T23:45",
    )
    write_ticket(
        build_ticket,
        ticket_id="T-542",
        task_type="code_build",
        status="open",
        project="demo-project",
        phase=2,
        wave="2B",
        blocked_by="[]",
    )
    write_brief_snapshot(
        snapshots_dir / "2026-04-08-creative-brief-wave2b-demo-project.md",
        project="demo-project",
        title="Creative Brief — Wave 2B Supplement",
        captured="2026-04-08T23:45",
        brief_scope="phase",
        phase=2,
        ticket="T-541",
        covered_waves='["Wave 2B"]',
    )
    write_brief_review(
        snapshots_dir / "2026-04-08-brief-review-wave2b-demo-project.md",
        project="demo-project",
        title="Brief Review — Wave 2B Supplement",
        updated="2026-04-08T23:50",
        phase=2,
        ticket="T-541",
        body_lines=["Reviewed `2026-04-08-creative-brief-wave2b-demo-project.md`."],
    )

    args = run_task_args(tmp_path, ticket_path=build_ticket)
    routed_task_types: list[str] = []
    built_agents: list[str] = []

    def fake_choose_agent(routing_arg, entries, task_type, ticket_tags=None, ticket_context=None):
        routed_task_types.append(task_type)
        return {
            "agent": "codex",
            "preferred": "codex",
            "reason": f"Routed by task_type={task_type}.",
            "pool": {},
            "agent_mode": "normal",
        }

    monkeypatch.setattr(agent_runtime, "reconcile_executor_ledgers", lambda ledger_dir: [])
    monkeypatch.setattr(agent_runtime, "load_effective_metering", lambda metering: (metering, "", []))
    monkeypatch.setattr(agent_runtime, "load_agent_routing", lambda platform: clone_routing(agent_runtime.DEFAULT_ROUTING))
    monkeypatch.setattr(agent_runtime, "load_quality_contract", lambda platform: {})
    monkeypatch.setattr(agent_runtime, "choose_agent", fake_choose_agent)
    monkeypatch.setattr(agent_runtime, "build_command", lambda agent, cli, prompt, cwd: built_agents.append(agent) or ["fake-agent"])
    monkeypatch.setattr(agent_runtime, "executor_ledger_dir", lambda: tmp_path / "data" / "executors")
    monkeypatch.setattr(agent_runtime.subprocess, "Popen", DummyProcess)

    returncode = agent_runtime.command_run_task(args)

    assert returncode == 0
    assert routed_task_types == ["code_build"]
    assert built_agents == ["codex"]


def test_project_scope_master_brief_ignores_phase_brief_cycle(tmp_path):
    agent_runtime = load_agent_runtime()
    tickets_dir = tmp_path / "tickets"
    master_ticket = tickets_dir / "T-731-creative-brief-project.md"
    phase_ticket = tickets_dir / "T-732-phase-0-creative-brief.md"

    write_ticket(
        master_ticket,
        ticket_id="T-731",
        task_type="creative_brief",
        status="open",
        project="demo-project",
        phase=0,
        wave="0A",
        blocked_by="[T-732]",
        extra_frontmatter={"tags": "[brief, creative-brief, project-scope]"},
    )
    master_text = master_ticket.read_text(encoding="utf-8")
    master_ticket.write_text(
        master_text.replace("# Example ticket", "# Example ticket\n\nThis is the project-level master contract."),
        encoding="utf-8",
    )

    write_ticket(
        phase_ticket,
        ticket_id="T-732",
        task_type="creative_brief",
        status="blocked",
        project="demo-project",
        phase=0,
        wave="0A",
        blocked_by="[T-731]",
        extra_frontmatter={"tags": "[brief, creative-brief, phase-scope]"},
    )

    unresolved = agent_runtime.unresolved_ticket_blockers(master_ticket)
    assert unresolved == []


def test_build_runtime_preamble_includes_gitnexus_guidance_for_code_tasks(monkeypatch):
    agent_runtime = load_agent_runtime()
    monkeypatch.setattr(
        agent_runtime,
        "load_project_code_context",
        lambda _ticket_context: {
            "available": True,
            "artifact_index_path": "/tmp/sample.artifact-index.yaml",
            "workspaces": [
                {
                    "root": "/tmp/sample-app",
                    "role": "primary",
                    "exists": True,
                    "git_repo": True,
                    "gitnexus_enabled": True,
                    "gitnexus_ready": True,
                }
            ],
            "live_workspaces": [
                {
                    "root": "/tmp/sample-app",
                    "role": "primary",
                    "exists": True,
                    "git_repo": True,
                    "gitnexus_enabled": True,
                    "gitnexus_ready": True,
                }
            ],
            "analyzable_workspaces": [
                {
                    "root": "/tmp/sample-app",
                    "role": "primary",
                    "exists": True,
                    "git_repo": True,
                    "gitnexus_enabled": True,
                    "gitnexus_ready": True,
                }
            ],
        },
    )

    code_context = agent_runtime.determine_code_intelligence_context(
        "code_build",
        "Refactor the approvals surface.",
        {"title": "Build approvals surface", "path": "/tmp/T-001.md"},
    )
    preamble = agent_runtime.build_runtime_preamble(
        "2026-04-13 13:00",
        agent_runtime.DEFAULT_QUALITY_CONTRACT,
        ticket_context={"title": "Build approvals surface"},
        nexus_context={"nexus_optional": False, "reason": ""},
        code_intelligence_context=code_context,
    )

    assert "Code-intelligence contract for this task" in preamble
    assert "GitNexus MCP" in preamble
    assert "`/tmp/sample-app`" in preamble


def test_build_executor_environment_includes_ticket_project_and_task_metadata(tmp_path):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, ticket_id="T-001", task_type="quality_check")

    env = agent_runtime.build_executor_environment(
        project="demo-project",
        client="demo-client",
        task_type="quality_check",
        ticket_path=ticket_path,
    )

    assert env["AGENT_PLATFORM_PROJECT"] == "demo-project"
    assert env["AGENT_PLATFORM_CLIENT"] == "demo-client"
    assert env["AGENT_PLATFORM_TASK_TYPE"] == "quality_check"
    assert env["AGENT_PLATFORM_TICKET_ID"] == "T-001"


def test_load_project_code_context_overlays_live_repo_and_ready_state(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()

    workspace = tmp_path / "sample-app"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "package.json").write_text('{"name":"demo"}\n', encoding="utf-8")
    subprocess.run(["git", "init"], cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=workspace, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "package.json"], cwd=workspace, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=workspace, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()

    project_root = tmp_path / "vault" / "clients" / "acme"
    tickets_dir = project_root / "tickets"
    projects_dir = project_root / "projects"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True, exist_ok=True)

    ticket_path = tickets_dir / "T-001.md"
    write_ticket(ticket_path, project="sample-project")
    sample_derived = projects_dir / "sample-project.derived"
    sample_derived.mkdir(parents=True, exist_ok=True)
    artifact_index = sample_derived / "artifact-index.yaml"
    artifact_index.write_text(
        "\n".join(
            [
                "project: sample-project",
                "client: acme",
                "code_workspaces:",
                f"  - root: {workspace}",
                f"    key: {workspace}",
                "    role: primary",
                "    exists: true",
                "    git_repo: false",
                "    gitnexus_enabled: true",
                "    gitnexus_ready: false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    state_path = tmp_path / "project_code_index_state.json"
    state_path.write_text(
        json.dumps(
            {
                "workspaces": {
                    str(workspace): {
                        "head": head,
                        "last_status": "refreshed",
                        "updated_at": "2026-04-14T00:01:00 EDT -0400",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(agent_runtime, "PROJECT_CODE_INDEX_STATE_PATH", state_path)

    context = agent_runtime.load_project_code_context({"path": str(ticket_path)})

    assert context["available"] is True
    assert context["workspaces"][0]["git_repo"] is True
    assert context["workspaces"][0]["gitnexus_ready"] is True
    assert context["analyzable_workspaces"][0]["root"] == str(workspace)


def test_load_agent_routing_reads_orchestration_context_config(tmp_path):
    agent_runtime = load_agent_runtime()
    platform_path = tmp_path / "platform.md"
    platform_path.write_text(
        "\n".join(
            [
                "# Platform",
                "",
                "## Agent Routing",
                "",
                "```yaml",
                "agent_routing:",
                "  agent_mode: normal",
                "  budget_based_routing: false",
                "  orchestration_context_mode: compact",
                "  orchestration_context_packet_max_chars: 9000",
                "  orchestration_context_expand_on: [phase_gate, system_anomaly]",
                "  agents:",
                "    claude:",
                "      cli: \"claude -p\"",
                "      enabled: true",
                "  task_routing:",
                "    orchestration: claude",
                "```",
            ]
        ),
        encoding="utf-8",
    )

    routing = agent_runtime.load_agent_routing(platform_path)

    assert routing["orchestration_context_mode"] == "compact"
    assert routing["orchestration_context_packet_max_chars"] == 9000
    assert routing["orchestration_context_expand_on"] == ["phase_gate", "system_anomaly"]


def test_build_orchestration_state_packet_is_compact_and_cited(tmp_path):
    agent_runtime = load_agent_runtime()
    project_root = tmp_path / "vault" / "clients" / "acme"
    projects_dir = project_root / "projects"
    tickets_dir = project_root / "tickets"
    project_file = projects_dir / "demo-project.md"
    project_file.parent.mkdir(parents=True, exist_ok=True)
    tickets_dir.mkdir(parents=True, exist_ok=True)
    project_file.write_text(
        "\n".join(
            [
                "---",
                "type: project",
                "project: demo-project",
                "---",
                "",
                "# Demo Project",
                "",
                "## Orchestrator Log",
                "",
                "- 2026-04-18T10:00: ORCH-CHECKPOINT: Assessed. One ticket active.",
                "- 2026-04-18T10:05: ORCH-CHECKPOINT: Spawned executor for T-001.",
            ]
        ),
        encoding="utf-8",
    )
    demo_derived = projects_dir / "demo-project.derived"
    demo_derived.mkdir(parents=True, exist_ok=True)
    (demo_derived / "current-context.md").write_text("# Current Context\n", encoding="utf-8")
    (demo_derived / "artifact-index.yaml").write_text("project: demo-project\n", encoding="utf-8")
    write_ticket(
        tickets_dir / "T-001-build.md",
        ticket_id="T-001",
        project="demo-project",
        status="in-progress",
        task_type="code_build",
        extra_frontmatter={
            "executor_agent": "codex",
            "executor_runtime_pid": "123",
            "executor_last_heartbeat": "2026-04-18T10:06",
        },
    )

    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)
    packet = agent_runtime.build_orchestration_state_packet(
        project_file=project_file,
        project_slug="demo-project",
        client="acme",
        local_now="2026-04-18T10:07 EDT -0400",
        routing=routing,
    )

    assert "Project file:" in packet
    assert "Current context:" in packet
    assert "T-001" in packet
    assert "status=in-progress" in packet
    assert "agent=codex" in packet
    assert "Spawned executor for T-001" in packet
    assert "Claude Escalation Rules" in packet


def test_build_orchestrator_prompt_modes_are_reversible(tmp_path):
    agent_runtime = load_agent_runtime()
    project_file = tmp_path / "vault" / "projects" / "demo-project.md"
    project_file.parent.mkdir(parents=True, exist_ok=True)
    project_file.write_text("# Demo Project\n", encoding="utf-8")
    routing = clone_routing(agent_runtime.DEFAULT_ROUTING)

    routing["orchestration_context_mode"] = "full"
    full_prompt = agent_runtime.build_orchestrator_prompt(
        local_now="2026-04-18T10:07 EDT -0400",
        project_slug="demo-project",
        client="_platform",
        project_file=project_file,
        routing=routing,
    )
    assert "Orchestration context mode is FULL" in full_prompt
    assert "state packet" not in full_prompt.lower()

    routing["orchestration_context_mode"] = "tiered"
    packet_path = tmp_path / "packet.md"
    tiered_prompt = agent_runtime.build_orchestrator_prompt(
        local_now="2026-04-18T10:07 EDT -0400",
        project_slug="demo-project",
        client="_platform",
        project_file=project_file,
        routing=routing,
        packet_path=packet_path,
    )
    assert "Orchestration context mode is TIERED" in tiered_prompt
    assert str(packet_path) in tiered_prompt
    assert "expand into exact canonical files" in tiered_prompt


def test_command_build_orchestrator_prompt_writes_packet(tmp_path, capsys):
    agent_runtime = load_agent_runtime()
    platform_path = tmp_path / "platform.md"
    platform_path.write_text(
        "\n".join(
            [
                "# Platform",
                "",
                "## Agent Routing",
                "",
                "```yaml",
                "agent_routing:",
                "  orchestration_context_mode: tiered",
                "  orchestration_context_packet_max_chars: 16000",
                "  task_routing:",
                "    orchestration: claude",
                "```",
            ]
        ),
        encoding="utf-8",
    )
    project_root = tmp_path / "vault" / "clients" / "acme"
    project_file = project_root / "projects" / "demo-project.md"
    project_file.parent.mkdir(parents=True, exist_ok=True)
    (project_root / "tickets").mkdir(parents=True, exist_ok=True)
    project_file.write_text("# Demo Project\n\n## Orchestrator Log\n", encoding="utf-8")
    packet_dir = tmp_path / "packets"

    result = agent_runtime.command_build_orchestrator_prompt(
        argparse.Namespace(
            platform=platform_path,
            project="demo-project",
            client="acme",
            project_file=project_file,
            packet_dir=packet_dir,
            local_now="2026-04-18T10:07 EDT -0400",
        )
    )
    captured = capsys.readouterr()

    assert result == 0
    assert "Orchestration context mode is TIERED" in captured.out
    packets = list(packet_dir.glob("orchestration-state-demo-project-20260418T1007.md"))
    assert len(packets) == 1
    assert "Orchestration State Packet" in packets[0].read_text(encoding="utf-8")
