from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECK_DELIVERY_GATE_PATH = REPO_ROOT / "scripts" / "check_delivery_gate.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_args(tmp_path: Path, *, require_visual_gate: bool, visual_gate_paths: list[str]) -> argparse.Namespace:
    return argparse.Namespace(
        verification_profile="general",
        claim_ledger_json=str(tmp_path / "claim-ledger.json"),
        credibility_report=str(tmp_path / "credibility-gate.md"),
        polish_gate_json=[str(tmp_path / "polish-gate.json")],
        stitch_gate_json=[],
        visual_gate_json=visual_gate_paths,
        fresh_checkout_json=[],
        verification_results_report=[],
        deliverables_root=str(tmp_path / "deliverable"),
        require_polish_gate=True,
        require_stitch_gate=False,
        require_visual_gate=require_visual_gate,
        fresh_checkout_mode="skip",
        verification_report_mode="skip",
        max_unverified=None,
        max_contradicted=None,
        max_stale=None,
        json_out=str(tmp_path / "out.json"),
        markdown_out=str(tmp_path / "out.md"),
    )


def prepare_common_inputs(tmp_path: Path) -> None:
    deliverable = tmp_path / "deliverable"
    deliverable.mkdir()
    (deliverable / "LIMITATIONS.md").write_text("# Limitations\n", encoding="utf-8")
    write_json(tmp_path / "claim-ledger.json", {"summary": {"CONTRADICTED": 0, "UNVERIFIED": 0, "STALE": 0}})
    (tmp_path / "credibility-gate.md").write_text("**Verdict:** PASS\n", encoding="utf-8")
    write_json(tmp_path / "polish-gate.json", {"verdict": "PASS"})


def test_delivery_gate_passes_when_visual_gate_passes(tmp_path):
    check_delivery_gate = load_module("check_delivery_gate_visual_pass", CHECK_DELIVERY_GATE_PATH)
    prepare_common_inputs(tmp_path)
    write_json(tmp_path / "visual-gate.json", {"verdict": "PASS"})

    report = check_delivery_gate.build_report(
        build_args(tmp_path, require_visual_gate=True, visual_gate_paths=[str(tmp_path / "visual-gate.json")])
    )
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "PASS"
    assert checks["visual_gate_pass"]["ok"] is True


def test_delivery_gate_fails_when_visual_gate_required_but_missing(tmp_path):
    check_delivery_gate = load_module("check_delivery_gate_visual_missing", CHECK_DELIVERY_GATE_PATH)
    prepare_common_inputs(tmp_path)

    report = check_delivery_gate.build_report(build_args(tmp_path, require_visual_gate=True, visual_gate_paths=[]))
    checks = {check["name"]: check for check in report["checks"]}

    assert report["verdict"] == "FAIL"
    assert checks["visual_gate_pass"]["ok"] is False
