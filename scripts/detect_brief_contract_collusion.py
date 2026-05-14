#!/usr/bin/env python3
"""Detect jointly thin brief and visual-specificity contract scores."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

THRESHOLD_SIGMA = 2.0


def utc_now() -> str:
    """Return a UTC ISO-8601 timestamp with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def brief_overall_score(data: dict[str, Any]) -> float:
    """Extract or derive a 0..1 brief specificity score."""
    if isinstance(data.get("overall_score"), (int, float)):
        return max(0.0, min(1.0, float(data["overall_score"])))
    axes = data.get("axis_scores")
    if isinstance(axes, dict) and axes:
        ratios: list[float] = []
        for axis in axes.values():
            if not isinstance(axis, dict):
                continue
            threshold = float(axis.get("threshold") or 0)
            count = float(axis.get("count") or 0)
            if threshold > 0:
                ratios.append(min(1.0, count / threshold))
        if ratios:
            return sum(ratios) / len(ratios)
    if data.get("overall_passes") is True or data.get("verdict") == "pass":
        return 1.0
    return 0.0


def vs_average_score(data: dict[str, Any]) -> float:
    """Extract the VS specificity average score."""
    if isinstance(data.get("average_score"), (int, float)):
        return max(0.0, min(1.0, float(data["average_score"])))
    item_scores = data.get("item_scores")
    if isinstance(item_scores, list) and item_scores:
        scores = [float(item.get("combined") or 0) for item in item_scores if isinstance(item, dict)]
        if scores:
            return max(0.0, min(1.0, sum(scores) / len(scores)))
    return 0.0


def baseline_from_file(path: Path | None) -> dict[str, Any] | None:
    """Read a historical baseline from flexible JSON shapes."""
    if path is None or not path.exists():
        return None
    data = load_json(path)
    if all(isinstance(data.get(key), (int, float)) for key in ("n", "mean", "stddev")):
        return {"n": int(data["n"]), "mean": float(data["mean"]), "stddev": float(data["stddev"])}
    for key in ("joint_scores", "scores", "samples"):
        values = data.get(key)
        if not isinstance(values, list):
            continue
        scores: list[float] = []
        for value in values:
            if isinstance(value, (int, float)):
                scores.append(float(value))
            elif isinstance(value, dict):
                raw = value.get("joint_score") or value.get("score")
                if isinstance(raw, (int, float)):
                    scores.append(float(raw))
        if len(scores) >= 2:
            stddev = statistics.stdev(scores)
            return {"n": len(scores), "mean": statistics.mean(scores), "stddev": stddev}
    return None


def detect_collusion(brief_json: Path, vs_json: Path, baseline_json: Path | None) -> dict[str, Any]:
    """Compute joint thinness and a z-score against historical baseline."""
    brief_data = load_json(brief_json)
    vs_data = load_json(vs_json)
    brief_score = brief_overall_score(brief_data)
    vs_score = vs_average_score(vs_data)
    joint_score = (brief_score + vs_score) / 2.0
    baseline = baseline_from_file(baseline_json)

    if not baseline or baseline.get("n", 0) < 5 or float(baseline.get("stddev") or 0) <= 0:
        return {
            "brief_score": round(brief_score, 4),
            "vs_score": round(vs_score, 4),
            "joint_score": round(joint_score, 4),
            "historical_baseline": baseline or {"n": 0, "mean": None, "stddev": None},
            "z_score": None,
            "threshold_sigma": THRESHOLD_SIGMA,
            "verdict": "cold_start",
            "recommended_action": "operator_review",
            "scanned_at": utc_now(),
        }

    mean = float(baseline["mean"])
    stddev = float(baseline["stddev"])
    z_score = (joint_score - mean) / stddev
    failed = math.isfinite(z_score) and z_score < -THRESHOLD_SIGMA
    return {
        "brief_score": round(brief_score, 4),
        "vs_score": round(vs_score, 4),
        "joint_score": round(joint_score, 4),
        "historical_baseline": {"n": int(baseline["n"]), "mean": round(mean, 4), "stddev": round(stddev, 4)},
        "z_score": round(z_score, 4),
        "threshold_sigma": THRESHOLD_SIGMA,
        "verdict": "fail" if failed else "pass",
        "recommended_action": "gate_block" if failed else "none",
        "scanned_at": utc_now(),
    }


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and optionally to a file."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief-score-json", required=True, help="Output from score_brief_specificity.py.")
    parser.add_argument("--vs-score-json", required=True, help="Output from score_specificity.py.")
    parser.add_argument("--historical-baseline", help="Optional historical baseline JSON.")
    parser.add_argument("--json-out", help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = detect_collusion(
            Path(args.brief_score_json).expanduser().resolve(),
            Path(args.vs_score_json).expanduser().resolve(),
            Path(args.historical_baseline).expanduser().resolve() if args.historical_baseline else None,
        )
        write_json(result, args.json_out)
        return 1 if result["verdict"] == "fail" else 0
    except Exception as exc:
        result = {
            "brief_score": None,
            "vs_score": None,
            "joint_score": None,
            "historical_baseline": None,
            "z_score": None,
            "threshold_sigma": THRESHOLD_SIGMA,
            "verdict": "fail",
            "recommended_action": "operator_review",
            "error": str(exc),
            "scanned_at": utc_now(),
        }
        write_json(result, args.json_out)
        return 1


if __name__ == "__main__":
    sys.exit(main())
