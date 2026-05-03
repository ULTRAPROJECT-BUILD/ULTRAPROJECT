#!/usr/bin/env python3
"""
Calibrate task-type time estimates from actual ticket execution data.

Scans all closed tickets, extracts actual duration from work log timestamps,
and writes calibrated per-task-type averages to data/calibrated_estimates.json.

Run periodically (e.g., after each runner cycle or daily) to keep estimates
accurate as the system learns from real execution patterns.

Usage:
    python3 scripts/calibrate_estimates.py
"""

import glob
import json
import os
import re
import statistics
from datetime import datetime

PLATFORM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_DIR = os.path.join(PLATFORM_DIR, "vault")
OUTPUT_FILE = os.path.join(PLATFORM_DIR, "data", "calibrated_estimates.json")

# Minimum samples before we trust calibrated data over defaults
MIN_SAMPLES = 2


def parse_frontmatter(filepath):
    """Extract YAML frontmatter as a simple dict."""
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except Exception:
        return {}, ""

    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    fm = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, parts[2]


def parse_work_log_timestamps(body):
    """Extract timestamps from work log entries."""
    timestamps = []
    in_log = False
    for line in body.splitlines():
        if line.strip() == "## Work Log":
            in_log = True
            continue
        if in_log and line.startswith("## "):
            break
        if in_log:
            m = re.match(r"^- (\d{4}-\d{2}-\d{2}T?\d{2}:\d{2})", line)
            if m:
                try:
                    ts = m.group(1)
                    if "T" in ts:
                        dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M")
                    else:
                        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M")
                    timestamps.append(dt)
                except ValueError:
                    pass
    return timestamps


def compute_actual_minutes(fm, body):
    """Compute actual execution minutes for a closed ticket.

    Strategy:
    1. Use work log timestamps: first agent-activity entry to last entry.
    2. Fall back to created→completed frontmatter fields.
    Returns None if we can't determine duration.
    """
    timestamps = parse_work_log_timestamps(body)

    if len(timestamps) >= 2:
        # Use work log span (more accurate than created→completed
        # since created may predate actual agent work)
        duration = (timestamps[-1] - timestamps[0]).total_seconds() / 60
        if 0 < duration <= 120:  # sanity: 0-120 min range
            return round(duration, 1)

    # Fall back to frontmatter
    created = fm.get("created", "")
    completed = fm.get("completed", "") or fm.get("updated", "")
    if created and completed:
        try:
            fmt = "%Y-%m-%dT%H:%M" if "T" in created else "%Y-%m-%d"
            dt_start = datetime.strptime(created[:16], fmt)
            fmt2 = "%Y-%m-%dT%H:%M" if "T" in completed else "%Y-%m-%d"
            dt_end = datetime.strptime(completed[:16], fmt2)
            duration = (dt_end - dt_start).total_seconds() / 60
            if 0 < duration <= 120:
                return round(duration, 1)
        except ValueError:
            pass

    return None


def scan_tickets():
    """Scan all closed tickets and collect actual durations by task type."""
    # task_type -> list of (actual_minutes, complexity)
    samples = {}

    ticket_paths = (
        glob.glob(os.path.join(VAULT_DIR, "tickets", "T-*.md"))
        + glob.glob(os.path.join(VAULT_DIR, "clients", "*/tickets/T-*.md"))
    )

    for path in ticket_paths:
        fm, body = parse_frontmatter(path)

        if fm.get("status") not in ("closed", "done"):
            continue

        task_type = fm.get("task_type", "general")
        complexity = fm.get("complexity", "standard")
        actual = compute_actual_minutes(fm, body)

        if actual is None:
            continue

        key = task_type
        if key not in samples:
            samples[key] = []
        samples[key].append({
            "minutes": actual,
            "complexity": complexity,
            "ticket": os.path.basename(path),
        })

    return samples


def build_calibrated_estimates(samples):
    """Build calibrated estimates from collected samples."""
    calibrated = {}

    for task_type, entries in samples.items():
        # Split by complexity
        standard = [e["minutes"] for e in entries if e["complexity"] != "deep"]
        deep = [e["minutes"] for e in entries if e["complexity"] == "deep"]

        result = {
            "sample_count": len(entries),
            "tickets": [e["ticket"] for e in entries],
        }

        if standard:
            result["standard_avg"] = round(statistics.mean(standard), 1)
            result["standard_median"] = round(statistics.median(standard), 1)
            result["standard_samples"] = len(standard)
        if deep:
            result["deep_avg"] = round(statistics.mean(deep), 1)
            result["deep_median"] = round(statistics.median(deep), 1)
            result["deep_samples"] = len(deep)

        # The calibrated estimate: use median (more robust to outliers)
        if standard and len(standard) >= MIN_SAMPLES:
            result["calibrated_minutes"] = result["standard_median"]
        elif standard:
            result["calibrated_minutes"] = result["standard_avg"]

        if deep and len(deep) >= MIN_SAMPLES:
            result["calibrated_deep_minutes"] = result["deep_median"]
        elif deep:
            result["calibrated_deep_minutes"] = result["deep_avg"]

        calibrated[task_type] = result

    return calibrated


def main():
    samples = scan_tickets()
    calibrated = build_calibrated_estimates(samples)

    output = {
        "generated": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "total_tickets_analyzed": sum(c["sample_count"] for c in calibrated.values()),
        "task_types": calibrated,
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"Calibrated estimates written to {OUTPUT_FILE}")
    print(f"Analyzed {output['total_tickets_analyzed']} closed tickets across {len(calibrated)} task types")
    for task_type, data in sorted(calibrated.items()):
        cal = data.get("calibrated_minutes", "?")
        deep_cal = data.get("calibrated_deep_minutes", "?")
        print(f"  {task_type}: standard={cal}min deep={deep_cal}min ({data['sample_count']} samples)")


if __name__ == "__main__":
    main()
