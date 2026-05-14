from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_visual_spec_gate


def test_gate_aborts_remaining_checks_when_runtime_budget_exceeded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    refs = tmp_path / "refs"
    refs.mkdir()
    json_out = tmp_path / "gate.json"
    profile = {
        "description": "runtime budget test",
        "checks": [1, 87, 88],
        "target_runtime_s": 1,
        "max_runtime_s": 5,
        "skip_policy": "pass",
        "cache_strategy": "none",
        "execution_mode": "sync",
    }

    def slow_check(ctx: check_visual_spec_gate.GateContext) -> dict[str, object]:
        check_visual_spec_gate.time.sleep(10)
        ctx.started_monotonic = check_visual_spec_gate.time.perf_counter() - 6
        return check_visual_spec_gate.make_check_result("pass", {"slept_seconds": 10})

    monkeypatch.setattr(check_visual_spec_gate, "get_profile", lambda _name: profile)
    monkeypatch.setattr(check_visual_spec_gate, "get_cache_categories", lambda _name: ())
    monkeypatch.setitem(check_visual_spec_gate.CHECK_RUNNERS, 1, slow_check)
    monkeypatch.setattr(check_visual_spec_gate.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_visual_spec_gate.py",
            "--references-dir",
            str(refs),
            "--medium",
            "web_ui",
            "--profile",
            "brief",
            "--json-out",
            str(json_out),
        ],
    )

    rc = check_visual_spec_gate.main()
    report = json.loads(json_out.read_text(encoding="utf-8"))
    checks = {item["id"]: item for item in report["checks"]}

    assert rc == 1
    assert report["verdict"] == "fail"
    assert report["budget_exceeded"] is True
    assert checks[1]["verdict"] == "pass"
    assert checks[87]["verdict"] == "not_run_runtime_budget_exceeded"
    assert checks[88]["verdict"] == "not_run_runtime_budget_exceeded"
    assert report["summary"]["not_run_runtime_budget_exceeded"] == 2
