#!/usr/bin/env python3
"""Run medium-aware preset regression replay against historical mockups."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from visual_spec_telemetry_common import (
    REGRESSION_SCHEMA_PATH,
    extract_json_object,
    load_frontmatter,
    load_markdown_with_frontmatter,
    platform_value,
    repo_relative,
    validate_artifact,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposed-change", required=True, help="Token mutation in AXIS_OR_TOKEN=VALUE form.")
    parser.add_argument("--preset", required=True, help="Preset name under evaluation.")
    parser.add_argument("--historical-vs-dir", required=True, help="Directory containing historical visual-spec artifacts or mockups.")
    parser.add_argument("--medium-plugin", required=True, help="Medium plugin markdown path.")
    parser.add_argument("--json-out", help="Optional JSON output path; also used for schema validation when present.")
    return parser.parse_args()


def parse_change(text: str) -> tuple[str, str]:
    """Parse AXIS=VALUE."""
    if "=" not in text:
        raise ValueError("proposed change must use AXIS_OR_TOKEN=VALUE form")
    key, value = text.split("=", 1)
    key = key.strip()
    if not key:
        raise ValueError("proposed change key is empty")
    return key, value.strip()


def load_contract(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load the medium plugin frontmatter and replay contract."""
    frontmatter = load_frontmatter(path)
    contract = frontmatter.get("regression_replay_contract")
    if not isinstance(contract, dict):
        contract = {
            "supported": False,
            "renderer_script": "scripts/regen_mockup.py",
            "required_source_artifacts": [],
            "supported_token_mutations": [],
            "unsupported_token_mutations": [],
            "unsupported_mutation_behavior": str(platform_value("visual_spec_regression_replay_fail_closed_default", "block_proposal")),
            "replay_fixture": "",
            "replay_determinism_test": "",
        }
    return frontmatter, contract


def mutation_supported(mutation: str, contract: dict[str, Any]) -> bool:
    """Return true when a mutation is replayable under the contract."""
    if contract.get("supported") is not True:
        return False
    unsupported = contract.get("unsupported_token_mutations")
    if isinstance(unsupported, list) and any(fnmatch.fnmatch(mutation, pattern) for pattern in unsupported if isinstance(pattern, str)):
        return False
    supported = contract.get("supported_token_mutations")
    if not isinstance(supported, list) or not supported:
        return True
    return any(fnmatch.fnmatch(mutation, pattern) for pattern in supported if isinstance(pattern, str))


def discover_html_mockups(root: Path) -> list[Path]:
    """Find HTML mockups directly or via VS markdown frontmatter."""
    html_paths = {path.resolve() for path in root.rglob("*.html") if path.is_file()}
    html_paths.update(path.resolve() for path in root.rglob("*.htm") if path.is_file())
    if html_paths:
        return sorted(html_paths)

    discovered: set[Path] = set()
    for md_path in root.rglob("*.md"):
        if not md_path.is_file():
            continue
        try:
            frontmatter, _body = load_markdown_with_frontmatter(md_path)
        except Exception:
            continue
        mockups = frontmatter.get("mockups")
        if not isinstance(mockups, list):
            continue
        for item in mockups:
            if not isinstance(item, dict):
                continue
            raw = str(item.get("final_html") or "").strip()
            if not raw:
                continue
            path = Path(raw)
            resolved = (md_path.parent / path).resolve() if not path.is_absolute() else path.resolve()
            if resolved.exists():
                discovered.add(resolved)
    return sorted(discovered)


def proposal_id(preset: str, mutation_key: str, proposed_value: str) -> str:
    """Build a stable proposal identifier."""
    slug = re.sub(r"[^a-z0-9._-]+", "-", f"{preset}-{mutation_key}-{proposed_value}".lower()).strip("-")
    return slug or "preset-regression"


def mutation_candidates(key: str) -> list[str]:
    """Generate CSS token name candidates from an axis/token path."""
    collapsed = key.replace(".", "-").replace("/", "-").replace("_", "-")
    return [f"--{collapsed}", key, collapsed]


def apply_mutation(html_text: str, key: str, proposed_value: str) -> tuple[str, int]:
    """Apply a best-effort token mutation to HTML/CSS text."""
    replacements = 0
    mutated = html_text
    for candidate in mutation_candidates(key):
        if candidate.startswith("--"):
            pattern = re.compile(rf"({re.escape(candidate)}\s*:\s*)([^;]+)(;)")
            mutated, changed = pattern.subn(rf"\1{proposed_value}\3", mutated)
            replacements += changed
        quoted_pattern = re.compile(rf'("{re.escape(candidate)}"\s*:\s*")([^"]+)(")')
        mutated, changed = quoted_pattern.subn(rf'\1{proposed_value}\3', mutated)
        replacements += changed
    return mutated, replacements


def run_regen(html_path: Path, png_path: Path, renderer_script: str) -> dict[str, Any]:
    """Render a mockup to PNG."""
    completed = subprocess.run(
        [sys.executable, str((SCRIPT_DIR.parent / renderer_script).resolve()), "--html", str(html_path), "--out-png", str(png_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=SCRIPT_DIR.parent,
    )
    if completed.returncode not in {0, 1, 2}:
        raise RuntimeError(f"regen_mockup.py exited {completed.returncode}: {completed.stderr.strip()}")
    payload = extract_json_object(completed.stdout)
    if completed.returncode != 0 and "error" in payload:
        raise RuntimeError(str(payload["error"]))
    return payload


def run_semantic_check(html_path: Path, medium: str) -> dict[str, Any]:
    """Run check_semantic_layout.py against a direct HTML file."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix="-semantic.json", delete=False) as handle:
        out_path = Path(handle.name)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str((SCRIPT_DIR / "check_semantic_layout.py").resolve()),
                "--vs-path",
                str(html_path),
                "--references-dir",
                str(html_path.parent),
                "--medium",
                medium,
                "--json-out",
                str(out_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=SCRIPT_DIR.parent,
        )
        if out_path.exists():
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        else:
            payload = extract_json_object(completed.stdout)
        if completed.returncode not in {0, 1} and payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        if payload.get("verdict") == "error":
            raise RuntimeError(str(payload.get("error") or "semantic layout helper failed"))
        return payload
    finally:
        try:
            out_path.unlink()
        except OSError:
            pass


def semantic_regression_items(project: str, mockup_path: Path, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Return regressions where a previously passing semantic check now fails."""
    items: list[dict[str, Any]] = []
    before_checks = before.get("checks", {})
    after_checks = after.get("checks", {})
    for key, before_check in before_checks.items():
        if key == "36_hierarchy_contrast":
            continue
        if not isinstance(before_check, dict):
            continue
        after_check = after_checks.get(key)
        if not isinstance(after_check, dict):
            continue
        if before_check.get("verdict") == "pass" and after_check.get("verdict") == "fail":
            items.append(
                {
                    "project": project,
                    "mockup_path": repo_relative(mockup_path),
                    "reason": f"{key} regressed: {after_check.get('details', 'failed after mutation')}",
                    "severity": "high" if key in {"37_pane_dominance", "40_density_target"} else "medium",
                }
            )
    return items


def hierarchy_regression_item(project: str, mockup_path: Path, before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Return hierarchy/contrast regression rows."""
    before_check = before.get("checks", {}).get("36_hierarchy_contrast")
    after_check = after.get("checks", {}).get("36_hierarchy_contrast")
    if not isinstance(before_check, dict) or not isinstance(after_check, dict):
        return []
    before_ratio = float(before_check.get("ratio") or 0.0)
    after_ratio = float(after_check.get("ratio") or 0.0)
    if before_check.get("verdict") == "pass" and after_check.get("verdict") == "fail":
        return [
            {
                "project": project,
                "mockup_path": repo_relative(mockup_path),
                "metric": "hierarchy_contrast",
                "before": round(before_ratio, 3),
                "after": round(after_ratio, 3),
            }
        ]
    return []


def infer_project(path: Path, root: Path) -> str:
    """Infer a project slug from path placement."""
    try:
        rel = path.resolve().relative_to(root.resolve())
        for part in rel.parts:
            if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", part):
                return part
    except ValueError:
        pass
    stem = re.sub(r"[^a-z0-9_-]+", "-", path.stem.lower()).strip("-")
    return stem or "unknown-project"


def validate_report_file(path: Path) -> dict[str, Any]:
    """Validate a regression report file."""
    return validate_artifact(path, REGRESSION_SCHEMA_PATH, "json")


def emit_operator_review(preset: str, medium: str, mutation_key: str, proposed_value: str, json_out: str | None, reason: str) -> dict[str, Any]:
    """Emit a schema-valid operator-review-required result."""
    payload = {
        "proposal_id": proposal_id(preset, mutation_key, proposed_value),
        "method": "simulate_only",
        "mockups_re_rendered": 0,
        "semantic_layout_regressions": [],
        "hierarchy_contrast_regressions": [],
        "pass": False,
        "regression_status": "operator_review_required",
        "unsupported_mediums": [medium] if medium else [],
    }
    if json_out:
        out_path = Path(json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validation = validate_report_file(out_path)
        if not validation.get("valid"):
            raise RuntimeError(f"regression report validation failed: {validation['errors']}")
    return payload


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    mutation_key, proposed_value = parse_change(args.proposed_change)
    medium_frontmatter, contract = load_contract(Path(args.medium_plugin).expanduser().resolve())
    medium = str(medium_frontmatter.get("medium") or "")
    if not mutation_supported(mutation_key, contract):
        return emit_operator_review(
            args.preset,
            medium,
            mutation_key,
            proposed_value,
            args.json_out,
            "mutation is not replay-supported for this medium",
        )

    historical_root = Path(args.historical_vs_dir).expanduser().resolve()
    mockups = discover_html_mockups(historical_root)
    if not mockups:
        return emit_operator_review(
            args.preset,
            medium,
            mutation_key,
            proposed_value,
            args.json_out,
            "no historical mockups were available to replay",
        )

    proposal_slug = proposal_id(args.preset, mutation_key, proposed_value)
    cache_root = (SCRIPT_DIR.parent / "vault" / "cache" / "visual-spec" / "regression" / proposal_slug).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)

    semantic_regressions: list[dict[str, Any]] = []
    hierarchy_regressions: list[dict[str, Any]] = []
    rerendered = 0
    renderer_script = str(contract.get("renderer_script") or "scripts/regen_mockup.py")

    for html_path in mockups:
        original_text = html_path.read_text(encoding="utf-8")
        mutated_text, replacements = apply_mutation(original_text, mutation_key, proposed_value)
        if replacements == 0:
            continue
        project = infer_project(html_path, historical_root)
        target_dir = cache_root / project / html_path.stem
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        original_copy = target_dir / html_path.name
        mutated_copy = target_dir / f"{html_path.stem}-mutated{html_path.suffix}"
        original_copy.write_text(original_text, encoding="utf-8")
        mutated_copy.write_text(mutated_text, encoding="utf-8")
        run_regen(original_copy, target_dir / "before.png", renderer_script)
        run_regen(mutated_copy, target_dir / "after.png", renderer_script)
        before = run_semantic_check(original_copy, medium)
        after = run_semantic_check(mutated_copy, medium)
        semantic_regressions.extend(semantic_regression_items(project, html_path, before, after))
        hierarchy_regressions.extend(hierarchy_regression_item(project, html_path, before, after))
        rerendered += 1

    if rerendered == 0:
        return emit_operator_review(
            args.preset,
            medium,
            mutation_key,
            proposed_value,
            args.json_out,
            "mutation did not match any replayable token sites",
        )

    payload = {
        "proposal_id": proposal_slug,
        "method": "real_rendering",
        "mockups_re_rendered": rerendered,
        "semantic_layout_regressions": semantic_regressions,
        "hierarchy_contrast_regressions": hierarchy_regressions,
        "pass": not semantic_regressions and not hierarchy_regressions,
        "regression_status": "pass" if not semantic_regressions and not hierarchy_regressions else "fail",
        "unsupported_mediums": [],
    }
    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validation = validate_report_file(out_path)
        if not validation.get("valid"):
            raise RuntimeError(f"regression report validation failed: {validation['errors']}")
    return payload


def main() -> int:
    args = parse_args()
    try:
        payload = build_payload(args)
        write_json(payload)
        return 0 if payload["regression_status"] in {"pass", "operator_review_required"} else 1
    except Exception as exc:
        payload = {
            "proposal_id": proposal_id(args.preset, *parse_change(args.proposed_change)),
            "method": "simulate_only",
            "mockups_re_rendered": 0,
            "semantic_layout_regressions": [],
            "hierarchy_contrast_regressions": [],
            "pass": False,
            "regression_status": "operator_review_required",
            "unsupported_mediums": [],
        }
        if args.json_out:
            out_path = Path(args.json_out).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(str(exc), file=sys.stderr)
        write_json(payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
