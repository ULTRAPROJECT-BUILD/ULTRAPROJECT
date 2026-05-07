from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "agent_runtime.py"


def load_agent_runtime():
    spec = importlib.util.spec_from_file_location("agent_runtime_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_ticket(path: Path, status: str = "open", blocked_by: str = "[T-100]") -> None:
    path.write_text(
        "\n".join(
            [
                "---",
                "type: ticket",
                "id: T-001",
                'title: "Example ticket"',
                f"status: {status}",
                "priority: high",
                "task_type: code_build",
                'project: "example-project"',
                "created: 2026-03-29T10:00",
                "updated: 2026-03-29T10:00",
                f"blocked_by: {blocked_by}",
                "---",
                "",
                "# Example ticket",
                "",
                "## Work Log",
                "",
                "- 2026-03-29T10:00: Created.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_mark_ticket_spawned_enforces_in_progress_state(tmp_path):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    ledger_path = tmp_path / "data" / "executors" / "T-001.json"
    write_ticket(ticket_path)

    agent_runtime.mark_ticket_spawned(
        ticket_path=ticket_path,
        agent_name="codex",
        task_type="code_build",
        runtime_pid=43210,
        ledger_path=ledger_path,
        routing_choice={
            "preferred": "codex",
            "reason": "codex is the preferred routed agent for code_build; budget-based routing is disabled.",
            "agent_mode": "normal",
        },
    )

    data = agent_runtime.parse_frontmatter_map(ticket_path)
    content = ticket_path.read_text(encoding="utf-8")

    assert data["status"] == "in-progress"
    assert data["blocked_by"] == []
    assert data["executor_agent"] == "codex"
    assert data["executor_preferred_agent"] == "codex"
    assert data["executor_routing_reason"] == "codex is the preferred routed agent for code_build; budget-based routing is disabled."
    assert data["executor_agent_mode"] == "normal"
    assert data["executor_task_type"] == "code_build"
    assert data["executor_runtime_pid"] == 43210
    assert data["executor_ledger"] == str(ledger_path)
    assert "Executor spawned via agent_runtime (codex, code_build)." in content
    assert "Routing: preferred=codex; actual=codex; mode=normal; reason=codex is the preferred routed agent for code_build; budget-based routing is disabled." in content


def test_reconcile_executor_ledgers_reopens_lost_in_progress_ticket(tmp_path):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    ledger_dir = tmp_path / "data" / "executors"
    ledger_path = ledger_dir / "T-001.json"
    write_ticket(ticket_path, status="in-progress", blocked_by="[]")

    agent_runtime.update_markdown_frontmatter(
        ticket_path,
        {
            "executor_agent": "codex",
            "executor_task_type": "code_fix",
            "executor_runtime_pid": 999991,
            "executor_child_pid": 999992,
            "executor_started": "2026-03-29T10:34",
            "executor_last_heartbeat": "2026-03-29T10:40",
            "executor_ledger": str(ledger_path),
        },
    )

    ledger_dir.mkdir(parents=True, exist_ok=True)
    agent_runtime.write_executor_ledger(
        ledger_path,
        {
            "ticket_id": "T-001",
            "ticket_path": str(ticket_path),
            "project": "example-project",
            "client": "example-client",
            "task_type": "code_fix",
            "agent": "codex",
            "cwd": str(tmp_path),
            "runtime_pid": 999991,
            "child_pid": 999992,
            "started_at": "2026-03-29T10:34",
            "last_heartbeat": "2026-03-29T10:40",
            "status": "running",
        },
    )

    recoveries = agent_runtime.reconcile_executor_ledgers(ledger_dir)
    data = agent_runtime.parse_frontmatter_map(ticket_path)
    content = ticket_path.read_text(encoding="utf-8")
    ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))

    assert recoveries == [
        {
            "ticket_id": "T-001",
            "ticket_path": str(ticket_path),
            "action": "reopened",
        }
    ]
    assert data["status"] == "open"
    assert "executor_agent" not in data
    assert "executor_preferred_agent" not in data
    assert "executor_routing_reason" not in data
    assert "executor_agent_mode" not in data
    assert "Executor lost (runtime PID 999991, child PID 999992). Reopened automatically by runtime recovery." in content
    assert ledger_payload["status"] == "recovered"
    assert ledger_payload["recovery_action"] == "reopened"


def test_reconcile_executor_ledgers_surfaces_last_recorded_termination_reason(tmp_path):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    ledger_dir = tmp_path / "data" / "executors"
    ledger_path = ledger_dir / "T-001.json"
    write_ticket(ticket_path, status="in-progress", blocked_by="[]")

    agent_runtime.update_markdown_frontmatter(
        ticket_path,
        {
            "executor_agent": "codex",
            "executor_task_type": "code_fix",
            "executor_runtime_pid": 999991,
            "executor_child_pid": 999992,
            "executor_started": "2026-03-29T10:34",
            "executor_last_heartbeat": "2026-03-29T10:40",
            "executor_ledger": str(ledger_path),
        },
    )

    ledger_dir.mkdir(parents=True, exist_ok=True)
    agent_runtime.write_executor_ledger(
        ledger_path,
        {
            "ticket_id": "T-001",
            "ticket_path": str(ticket_path),
            "project": "example-project",
            "client": "example-client",
            "task_type": "code_fix",
            "agent": "codex",
            "cwd": str(tmp_path),
            "runtime_pid": 999991,
            "child_pid": 999992,
            "started_at": "2026-03-29T10:34",
            "last_heartbeat": "2026-03-29T10:40",
            "status": "running",
            "exit_code": 137,
            "termination_reason": "terminated_by_signal_9",
        },
    )

    agent_runtime.reconcile_executor_ledgers(ledger_dir)
    content = ticket_path.read_text(encoding="utf-8")
    ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))

    assert "Last recorded termination: terminated_by_signal_9 (exit code 137)." in content
    assert ledger_payload["status"] == "recovered"
    assert ledger_payload["termination_reason"] == "terminated_by_signal_9"
    assert ledger_payload["exit_code"] == 137


def test_finalize_ticket_after_failed_executor_reopens_ticket(tmp_path):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    write_ticket(ticket_path, status="in-progress", blocked_by="[]")

    agent_runtime.update_markdown_frontmatter(
        ticket_path,
        {
            "executor_agent": "codex",
            "executor_task_type": "code_build",
            "executor_runtime_pid": 12345,
            "executor_child_pid": 12346,
            "executor_started": "2026-03-29T11:00",
            "executor_last_heartbeat": "2026-03-29T11:01",
            "executor_ledger": "/tmp/fake-ledger.json",
        },
    )

    agent_runtime.finalize_ticket_after_executor(ticket_path, returncode=9)
    data = agent_runtime.parse_frontmatter_map(ticket_path)
    content = ticket_path.read_text(encoding="utf-8")

    assert data["status"] == "open"
    assert "executor_agent" not in data
    assert "executor_preferred_agent" not in data
    assert "executor_routing_reason" not in data
    assert "executor_agent_mode" not in data
    assert "Executor exited unexpectedly with code 9. Reopened by agent_runtime." in content


def test_reconcile_executor_ledgers_cleans_closed_ticket_with_stale_live_executor(tmp_path, monkeypatch):
    agent_runtime = load_agent_runtime()
    ticket_path = tmp_path / "T-001-example.md"
    ledger_dir = tmp_path / "data" / "executors"
    ledger_path = ledger_dir / "T-001.json"
    write_ticket(ticket_path, status="closed", blocked_by="[]")

    agent_runtime.update_markdown_frontmatter(
        ticket_path,
        {
            "completed": "2026-03-29T11:45",
            "executor_agent": "claude",
            "executor_task_type": "general",
            "executor_runtime_pid": 999991,
            "executor_child_pid": 999992,
            "executor_started": "2026-03-29T11:00",
            "executor_last_heartbeat": "2026-03-29T11:40",
            "executor_ledger": str(ledger_path),
        },
    )

    ledger_dir.mkdir(parents=True, exist_ok=True)
    agent_runtime.write_executor_ledger(
        ledger_path,
        {
            "ticket_id": "T-001",
            "ticket_path": str(ticket_path),
            "project": "example-project",
            "client": "example-client",
            "task_type": "general",
            "agent": "claude",
            "cwd": str(tmp_path),
            "runtime_pid": 999991,
            "child_pid": 999992,
            "started_at": "2026-03-29T11:00",
            "last_heartbeat": "2026-03-29T11:40",
            "status": "running",
        },
    )

    monkeypatch.setattr(
        agent_runtime,
        "is_process_alive",
        lambda pid: pid in {999991, 999992},
    )
    terminated: list[tuple[int | None, int | None]] = []
    monkeypatch.setattr(
        agent_runtime,
        "terminate_executor_processes",
        lambda runtime_pid, child_pid: terminated.append((runtime_pid, child_pid)),
    )

    recoveries = agent_runtime.reconcile_executor_ledgers(ledger_dir)
    data = agent_runtime.parse_frontmatter_map(ticket_path)
    ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8"))

    assert recoveries == [
        {
            "ticket_id": "T-001",
            "ticket_path": str(ticket_path),
            "action": "cleaned_terminal",
        }
    ]
    assert terminated == [(999991, 999992)]
    assert data["status"] == "closed"
    assert "executor_agent" not in data
    assert "executor_preferred_agent" not in data
    assert "executor_routing_reason" not in data
    assert "executor_agent_mode" not in data
    assert ledger_payload["status"] == "completed"
    assert ledger_payload["recovery_action"] == "cleaned_terminal_closed"
