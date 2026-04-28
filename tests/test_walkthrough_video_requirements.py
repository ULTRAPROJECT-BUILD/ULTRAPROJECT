from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_REVIEW_PACK_PATH = REPO_ROOT / "scripts" / "build_review_pack.py"
CHECK_POLISH_GATE_PATH = REPO_ROOT / "scripts" / "check_polish_gate.py"
ENSURE_QC_WALKTHROUGH_PATH = REPO_ROOT / "scripts" / "ensure_qc_walkthrough.py"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_review_pack_args(root: Path, *, briefs: list[Path] | None = None, qc_reports: list[Path] | None = None):
    return argparse.Namespace(
        deliverables_root=str(root),
        brief=[str(path) for path in (briefs or [])],
        qc_report=[str(path) for path in (qc_reports or [])],
        max_files_per_category=12,
        json_out=str(root / "unused.json"),
        markdown_out=str(root / "unused.md"),
    )


def polish_gate_args(polish_report: Path, review_pack_json: Path):
    return argparse.Namespace(
        polish_report=str(polish_report),
        review_pack_json=str(review_pack_json),
        required_grade="A",
        json_out=str(polish_report.parent / "unused-gate.json"),
        markdown_out=str(polish_report.parent / "unused-gate.md"),
    )


def write_polish_report(path: Path, *, mention_walkthrough: bool = False) -> None:
    walkthrough_line = "Reviewed qc-walkthrough.mp4 as part of the interaction pass.\n\n" if mention_walkthrough else ""
    path.write_text(
        "\n".join(
            [
                "---",
                'verdict: "PASS"',
                'grade: "A"',
                "---",
                "",
                "## Verdict: PASS",
                "",
                "## Grade: A",
                "",
                "## Top Findings",
                "",
                "- None.",
                "",
                "## First Impression",
                "",
                walkthrough_line + "Credible and complete.",
                "",
                "## Coherence",
                "",
                "Strong.",
                "",
                "## Specificity",
                "",
                "Specific to the project.",
                "",
                "## Friction",
                "",
                "Low.",
                "",
                "## Edge Finish",
                "",
                "Clean.",
                "",
                "## Trust",
                "",
                "High.",
                "",
                "## Delta Quality",
                "",
                "N/A",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_review_pack_requires_walkthrough_for_packaged_app(tmp_path):
    build_review_pack = load_module("build_review_pack_under_test", BUILD_REVIEW_PACK_PATH)
    root = tmp_path / "deliverables"
    (root / "Demo.app").mkdir(parents=True)

    report = build_review_pack.build_report(build_review_pack_args(root))

    assert report["walkthrough_requirement"]["level"] == "required"
    assert "application artifact" in report["walkthrough_requirement"]["reasons"][0].lower()


def test_build_review_pack_requires_walkthrough_for_interactive_html_from_brief(tmp_path):
    build_review_pack = load_module("build_review_pack_under_test", BUILD_REVIEW_PACK_PATH)
    root = tmp_path / "dashboard-deliverables"
    root.mkdir()
    (root / "index.html").write_text("<html><body>app</body></html>", encoding="utf-8")
    brief = tmp_path / "brief.md"
    brief.write_text("Build an interactive dashboard web app with a multi-step settings flow.", encoding="utf-8")

    report = build_review_pack.build_report(build_review_pack_args(root, briefs=[brief]))

    assert report["walkthrough_requirement"]["level"] == "required"


def test_build_review_pack_only_recommends_walkthrough_for_static_html(tmp_path):
    build_review_pack = load_module("build_review_pack_under_test", BUILD_REVIEW_PACK_PATH)
    root = tmp_path / "marketing-site"
    root.mkdir()
    (root / "index.html").write_text("<html><body>marketing</body></html>", encoding="utf-8")
    brief = tmp_path / "brief.md"
    brief.write_text("Build a marketing landing page for the company website.", encoding="utf-8")

    report = build_review_pack.build_report(build_review_pack_args(root, briefs=[brief]))

    assert report["walkthrough_requirement"]["level"] == "recommended"


def test_polish_gate_fails_when_required_walkthrough_is_missing(tmp_path):
    check_polish_gate = load_module("check_polish_gate_under_test", CHECK_POLISH_GATE_PATH)
    review_pack_json = tmp_path / "review-pack.json"
    review_pack_json.write_text(
        json.dumps(
            {
                "verdict": "PASS",
                "spotlight_artifacts": [{"path": "/tmp/app", "relative_path": "Demo.app", "category": "application"}],
                "walkthrough_artifacts": [],
                "walkthrough_requirement": {"level": "required", "reasons": ["Packaged app detected."]},
            }
        ),
        encoding="utf-8",
    )
    polish_report = tmp_path / "polish.md"
    write_polish_report(polish_report, mention_walkthrough=False)

    report = check_polish_gate.build_report(polish_gate_args(polish_report, review_pack_json))

    assert report["verdict"] == "FAIL"
    assert any(check["name"] == "walkthrough_present_when_required" and not check["ok"] for check in report["checks"])


def test_polish_gate_passes_when_required_walkthrough_is_present_and_referenced(tmp_path):
    check_polish_gate = load_module("check_polish_gate_under_test", CHECK_POLISH_GATE_PATH)
    review_pack_json = tmp_path / "review-pack.json"
    review_pack_json.write_text(
        json.dumps(
            {
                "verdict": "PASS",
                "spotlight_artifacts": [{"path": "/tmp/app", "relative_path": "Demo.app", "category": "application"}],
                "walkthrough_artifacts": [
                    {
                        "path": "/tmp/qc-walkthrough.mp4",
                        "relative_path": "qc-walkthrough.mp4",
                        "name": "qc-walkthrough.mp4",
                        "category": "media",
                        "size_bytes": 10,
                    }
                ],
                "walkthrough_requirement": {"level": "required", "reasons": ["Packaged app detected."]},
            }
        ),
        encoding="utf-8",
    )
    polish_report = tmp_path / "polish.md"
    write_polish_report(polish_report, mention_walkthrough=True)

    report = check_polish_gate.build_report(polish_gate_args(polish_report, review_pack_json))

    assert report["verdict"] == "PASS"


def test_ensure_qc_walkthrough_plans_web_capture_for_interactive_html(tmp_path):
    ensure_qc_walkthrough = load_module("ensure_qc_walkthrough_under_test", ENSURE_QC_WALKTHROUGH_PATH)
    root = tmp_path / "dashboard-deliverables"
    root.mkdir()
    (root / "index.html").write_text("<html><body>dashboard</body></html>", encoding="utf-8")
    brief = tmp_path / "brief.md"
    brief.write_text("Interactive dashboard web app with a multi-step wizard.", encoding="utf-8")

    plan = ensure_qc_walkthrough.plan_capture(
        deliverables_root=root,
        brief_paths=[brief],
        qc_paths=[],
        explicit_url=None,
        explicit_launch_path=None,
        output_path=root / "qc-walkthrough.mp4",
    )

    assert plan["requirement"]["level"] == "required"
    assert plan["mode"] == "web"
    assert plan["url"].startswith("file://")


def test_ensure_qc_walkthrough_plans_desktop_capture_for_app_bundle(tmp_path):
    ensure_qc_walkthrough = load_module("ensure_qc_walkthrough_under_test", ENSURE_QC_WALKTHROUGH_PATH)
    root = tmp_path / "deliverables"
    app_bundle = root / "Demo.app"
    app_bundle.mkdir(parents=True)

    plan = ensure_qc_walkthrough.plan_capture(
        deliverables_root=root,
        brief_paths=[],
        qc_paths=[],
        explicit_url=None,
        explicit_launch_path=None,
        output_path=root / "qc-walkthrough.mp4",
    )

    assert plan["requirement"]["level"] == "required"
    assert plan["mode"] == "desktop"
    assert plan["launch_path"] == str(app_bundle.resolve())


def test_ensure_qc_walkthrough_reuses_existing_video(tmp_path):
    ensure_qc_walkthrough = load_module("ensure_qc_walkthrough_under_test", ENSURE_QC_WALKTHROUGH_PATH)
    root = tmp_path / "deliverables"
    root.mkdir()
    (root / "qc-walkthrough.mp4").write_bytes(b"video")

    plan = ensure_qc_walkthrough.plan_capture(
        deliverables_root=root,
        brief_paths=[],
        qc_paths=[],
        explicit_url=None,
        explicit_launch_path=None,
        output_path=root / "qc-walkthrough.mp4",
    )

    assert plan["status"] == "existing"
    assert plan["mode"] == "existing"
