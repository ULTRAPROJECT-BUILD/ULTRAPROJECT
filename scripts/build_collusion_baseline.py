#!/usr/bin/env python3
"""Build the historical baseline for brief/VS collusion detection."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
VAULT_ROOT = REPO_ROOT / "vault"
DEFAULT_OUT = VAULT_ROOT / "config" / "brief-contract-collusion-baseline.json"
DEFAULT_TAXONOMY = VAULT_ROOT / "archive" / "visual-aesthetics" / "_banned_vague_taxonomy.md"
MIN_SAMPLES = 5

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import detect_brief_contract_collusion as collusion
import extract_specificity_candidates as candidates
import score_brief_specificity
import score_specificity


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_frontmatter(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("PyYAML is required to read visual spec frontmatter.") from exc
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            loaded = yaml.safe_load("\n".join(lines[1:index])) or {}
            return loaded if isinstance(loaded, dict) else {}
    return {}


def project_from_path(path: Path, frontmatter: dict[str, Any]) -> str:
    value = str(frontmatter.get("project") or "").strip()
    if value:
        return value
    for parent in path.parents:
        if parent.name not in {"visual-references", "snapshots", "clients", "vault"}:
            return parent.name
    return path.stem


def candidate_roots(vault_root: Path) -> list[Path]:
    roots = [vault_root / "snapshots"]
    clients = vault_root / "clients"
    if clients.exists():
        roots.extend(path / "snapshots" for path in clients.iterdir() if path.is_dir())
    return [root for root in roots if root.exists()]


def iter_visual_specs(roots: list[Path]) -> list[Path]:
    seen: set[str] = set()
    results: list[Path] = []
    for root in roots:
        for path in root.rglob("*.md"):
            name = path.name.lower()
            if "visual-spec" not in name:
                continue
            if "waiver" in name or "gate" in name:
                continue
            resolved = path.resolve()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            results.append(resolved)
    return sorted(results)


def find_brief(vs_path: Path) -> Path | None:
    search_dirs = [vs_path.parent, *vs_path.parents[:4]]
    for directory in search_dirs:
        direct = directory / "brief.md"
        if direct.exists():
            return direct.resolve()
        matches = sorted(
            path
            for path in directory.glob("*brief*.md")
            if path.is_file() and "elaboration" not in path.name.lower() and "clarification" not in path.name.lower()
        )
        if matches:
            return matches[0].resolve()
    return None


def score_vs_against_brief(vs_path: Path, brief_path: Path, project: str, temp_dir: Path) -> dict[str, Any]:
    brief_text = brief_path.read_text(encoding="utf-8")
    taxonomy_text = DEFAULT_TAXONOMY.read_text(encoding="utf-8")
    raw_candidates = candidates.stub_extract(brief_text, taxonomy_text)
    payload = candidates.normalize_payload(
        raw_candidates,
        project=project,
        client=None,
        brief_path=brief_path,
        brief_text=brief_text,
        extractor="stub",
    )
    candidates.validate_schema(payload)
    candidate_path = temp_dir / f"{project}-{abs(hash(str(vs_path))) % 100000000}-candidates.json"
    candidate_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return score_specificity.score_contract(vs_path, candidate_path, DEFAULT_TAXONOMY)


def collect_samples(vault_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    samples: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    roots = candidate_roots(vault_root)
    with tempfile.TemporaryDirectory(prefix="oneshot-collusion-baseline-") as tmp:
        temp_dir = Path(tmp)
        for vs_path in iter_visual_specs(roots):
            frontmatter = load_frontmatter(vs_path)
            project = project_from_path(vs_path, frontmatter)
            brief_path = find_brief(vs_path)
            if brief_path is None:
                skipped.append({"vs_path": str(vs_path), "reason": "brief_not_found"})
                continue
            try:
                brief_score = score_brief_specificity.score_brief(brief_path)
                vs_score = score_vs_against_brief(vs_path, brief_path, project, temp_dir)
                brief_value = collusion.brief_overall_score(brief_score)
                vs_value = collusion.vs_average_score(vs_score)
            except Exception as exc:
                skipped.append({"vs_path": str(vs_path), "brief_path": str(brief_path), "reason": str(exc)})
                continue
            joint_score = (brief_value + vs_value) / 2.0
            samples.append(
                {
                    "project": project,
                    "brief_path": str(brief_path),
                    "vs_path": str(vs_path),
                    "brief_score": round(brief_value, 4),
                    "vs_score": round(vs_value, 4),
                    "joint_score": round(joint_score, 4),
                }
            )
    return samples, skipped


def build_baseline(samples: list[dict[str, Any]], skipped: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [float(sample["joint_score"]) for sample in samples]
    if len(scores) < MIN_SAMPLES:
        return {
            "verdict": "insufficient_samples",
            "n": len(scores),
            "min_samples": MIN_SAMPLES,
            "generated_at": utc_now(),
            "samples": samples,
            "skipped": skipped,
        }
    return {
        "verdict": "baseline_ready",
        "n": len(scores),
        "mean": round(statistics.mean(scores), 6),
        "stddev": round(statistics.stdev(scores), 6) if len(scores) >= 2 else 0.0,
        "generated_at": utc_now(),
        "samples": samples,
        "skipped": skipped,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault-root", default=str(VAULT_ROOT), help="Vault root to scan.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Baseline JSON output path.")
    parser.add_argument("--min-samples", type=int, default=MIN_SAMPLES, help="Minimum samples required before writing baseline.")
    parser.add_argument("--force-write-insufficient", action="store_true", help="Write a diagnostic JSON even with too few samples.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global MIN_SAMPLES
    MIN_SAMPLES = max(1, int(args.min_samples))
    vault_root = Path(args.vault_root).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    samples, skipped = collect_samples(vault_root)
    payload = build_baseline(samples, skipped)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if payload["verdict"] == "baseline_ready" or args.force_write_insufficient:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
