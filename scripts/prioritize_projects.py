#!/usr/bin/env python3
"""
Prioritize active projects by estimated time to delivery.

Shortest-remaining-job first, with aging bonus for older projects.

Usage:
    python3 scripts/prioritize_projects.py [project_file_paths...]

Reads project files and their tickets, scores each project, and prints
the project file paths in priority order (highest priority first).

Scoring:
    - Fewer remaining open/in-progress tickets = higher priority (ships faster)
    - Older projects get a bonus (prevents starvation)
    - Deep/complex tickets count as 3 standard tickets
    - Projects with only 1-2 tickets left get a big bonus (almost done)
"""

import json
import os
import re
import sys
import glob
from datetime import datetime


def parse_frontmatter(filepath):
    """Extract YAML frontmatter as a simple dict."""
    try:
        with open(filepath, "r") as f:
            content = f.read()
    except Exception:
        return {}

    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    fm = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


# Default estimates — used when no calibrated data exists for a task type
DEFAULT_TASK_TYPE_MINUTES = {
    # Fast tasks (< 5 min)
    "general": 5,
    "email_composition": 3,
    "vault_navigation": 2,
    # Medium tasks (5-15 min)
    "creative_brief": 10,
    "self_review": 8,
    "onboarding": 5,
    "code_review": 5,
    "code_fix": 8,
    "test_generation": 8,
    "mcp_review": 5,
    # Heavy tasks (15+ min)
    "code_build": 15,
    "mcp_build": 15,
    "orchestration": 10,
    "inbox_processor": 5,
    "artifact_cleanup": 3,
    "receipt_cleanup": 3,
    "docs_cleanup": 4,
    "data_enrichment": 20,
}

# Deep complexity multiplier (used when no calibrated deep estimate exists)
DEEP_MULTIPLIER = 2.0

# Load calibrated estimates from data/calibrated_estimates.json if available
CALIBRATED_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "calibrated_estimates.json",
)
_calibrated_cache = None


def _load_calibrated():
    """Load calibrated estimates, caching the result."""
    global _calibrated_cache
    if _calibrated_cache is not None:
        return _calibrated_cache
    try:
        with open(CALIBRATED_FILE, "r") as f:
            data = json.load(f)
        _calibrated_cache = data.get("task_types", {})
    except (FileNotFoundError, json.JSONDecodeError):
        _calibrated_cache = {}
    return _calibrated_cache


def get_task_estimate(task_type, complexity):
    """Get estimated minutes for a task, preferring calibrated data."""
    calibrated = _load_calibrated()
    cal = calibrated.get(task_type)

    if cal and complexity == "deep" and "calibrated_deep_minutes" in cal:
        return cal["calibrated_deep_minutes"]

    if cal and "calibrated_minutes" in cal:
        base = cal["calibrated_minutes"]
        return base * DEEP_MULTIPLIER if complexity == "deep" else base

    # Fall back to defaults
    base = DEFAULT_TASK_TYPE_MINUTES.get(task_type, 10)
    if complexity == "deep":
        base *= DEEP_MULTIPLIER
    return base


def estimate_remaining_minutes(project_file):
    """Estimate total remaining wall-clock minutes for a project."""
    fm = parse_frontmatter(project_file)

    # Determine ticket directory
    if "/clients/" in project_file:
        client_dir = project_file.split("/clients/")[1].split("/projects/")[0]
        base = project_file.split("/clients/")[0]
        ticket_dir = os.path.join(base, "clients", client_dir, "tickets")
    else:
        base = os.path.dirname(os.path.dirname(project_file))
        ticket_dir = os.path.join(base, "tickets")

    if not os.path.isdir(ticket_dir):
        return 0, 0, 0

    estimated_minutes = 0
    remaining_count = 0
    total_tickets = 0

    for ticket_file in glob.glob(os.path.join(ticket_dir, "T-*.md")) + glob.glob(os.path.join(ticket_dir, "PT-*.md")):
        tfm = parse_frontmatter(ticket_file)

        # Only count tickets belonging to this project — match on exact slug only
        ticket_project = tfm.get("project", "")
        project_basename = os.path.basename(project_file).replace(".md", "")
        if not ticket_project or ticket_project != project_basename:
            continue

        total_tickets += 1
        status = tfm.get("status", "closed")

        if status in ("open", "in-progress", "blocked", "waiting"):
            remaining_count += 1
            task_type = tfm.get("task_type", "general")
            complexity = tfm.get("complexity", "standard")
            base_minutes = get_task_estimate(task_type, complexity)

            # Waiting/blocked tickets still count but at reduced weight
            # (they need something external before they can run)
            if status in ("waiting", "blocked"):
                base_minutes *= 0.5

            estimated_minutes += base_minutes

    return estimated_minutes, remaining_count, total_tickets


def get_project_age_hours(project_file):
    """Get project age in hours from creation date."""
    fm = parse_frontmatter(project_file)
    created = fm.get("created", "")

    try:
        if "T" in created:
            dt = datetime.strptime(created[:16], "%Y-%m-%dT%H:%M")
        else:
            dt = datetime.strptime(created[:10], "%Y-%m-%d")
        age = datetime.now() - dt
        return age.total_seconds() / 3600
    except Exception:
        return 0


def get_deadline_urgency(project_file):
    """Get deadline urgency bonus. Returns (bonus, hours_until_due).

    Urgency ramps up as the deadline approaches:
    - >48h away: no bonus
    - 24-48h: moderate bonus (-50)
    - 12-24h: strong bonus (-100)
    - 6-12h: urgent bonus (-200)
    - <6h: critical bonus (-400)
    - overdue: maximum bonus (-500)
    """
    fm = parse_frontmatter(project_file)
    due = fm.get("due", "")
    if not due:
        return 0, None

    try:
        if "T" in due:
            due_dt = datetime.strptime(due[:16], "%Y-%m-%dT%H:%M")
        else:
            due_dt = datetime.strptime(due[:10], "%Y-%m-%d")
        hours_left = (due_dt - datetime.now()).total_seconds() / 3600

        if hours_left < 0:
            return -500, hours_left  # overdue
        elif hours_left < 6:
            return -400, hours_left  # critical
        elif hours_left < 12:
            return -200, hours_left  # urgent
        elif hours_left < 24:
            return -100, hours_left  # strong
        elif hours_left < 48:
            return -50, hours_left   # moderate
        else:
            return 0, hours_left     # plenty of time
    except Exception:
        return 0, None


def has_admin_priority(project_file):
    """Check if the project itself is tagged admin-priority."""
    fm = parse_frontmatter(project_file)
    tags = fm.get("tags", "")
    return "admin-priority" in tags


def has_next_up_priority(project_file):
    """Check whether the project is explicitly marked as the next project to run."""
    fm = parse_frontmatter(project_file)
    next_up = fm.get("next_up", "")
    if str(next_up).lower() == "true":
        return True
    tags = fm.get("tags", "")
    return "next-up" in tags


def has_critical_priority(project_file):
    """Check if any open ticket for this project has priority: critical."""
    if "/clients/" in project_file:
        client_dir = project_file.split("/clients/")[1].split("/projects/")[0]
        base = project_file.split("/clients/")[0]
        ticket_dir = os.path.join(base, "clients", client_dir, "tickets")
    else:
        base = os.path.dirname(os.path.dirname(project_file))
        ticket_dir = os.path.join(base, "tickets")

    if not os.path.isdir(ticket_dir):
        return False

    project_slug = os.path.basename(project_file).replace(".md", "")
    for ticket_file in glob.glob(os.path.join(ticket_dir, "T-*.md")) + glob.glob(os.path.join(ticket_dir, "PT-*.md")):
        tfm = parse_frontmatter(ticket_file)
        if tfm.get("project", "") != project_slug:
            continue
        if tfm.get("status", "") in ("open", "in-progress", "waiting", "blocked"):
            if tfm.get("priority", "").lower() == "critical":
                return True
    return False


def get_phase_state(project_file):
    """Check if the project has remaining phases in its project plan snapshot.

    Returns (current_phase, total_phases) or (None, None) if no plan found.
    """
    project_slug = os.path.basename(project_file).replace(".md", "")

    if "/clients/" in project_file:
        client_dir = project_file.split("/clients/")[1].split("/projects/")[0]
        base = project_file.split("/clients/")[0]
        snapshots_dir = os.path.join(base, "clients", client_dir, "snapshots")
    else:
        base = os.path.dirname(os.path.dirname(project_file))
        snapshots_dir = os.path.join(base, "snapshots")

    if not os.path.isdir(snapshots_dir):
        return None, None

    best_phase = None
    best_total = None
    best_ts = ""

    for snap_file in glob.glob(os.path.join(snapshots_dir, "*project-plan*.md")):
        sfm = parse_frontmatter(snap_file)
        if sfm.get("subtype") != "project-plan":
            continue
        if sfm.get("project", "") != project_slug:
            continue
        snap_ts = sfm.get("updated", sfm.get("captured", ""))
        if snap_ts >= best_ts:
            best_ts = snap_ts
            try:
                best_phase = int(sfm.get("current_phase", -1))
                best_total = int(sfm.get("total_phases", -1))
            except (ValueError, TypeError):
                best_phase = None
                best_total = None

    return best_phase, best_total


def score_project(project_file):
    """
    Score a project for priority. LOWER score = HIGHER priority.

    Based on estimated wall-clock minutes to next delivery, with age bonus,
    deadline urgency, and critical ticket priority.
    """
    est_minutes, remaining, total = estimate_remaining_minutes(project_file)
    age_hours = get_project_age_hours(project_file)
    deadline_bonus, hours_until_due = get_deadline_urgency(project_file)
    is_critical = has_critical_priority(project_file)
    is_admin_priority = has_admin_priority(project_file)
    is_next_up = has_next_up_priority(project_file)

    # Base score = estimated minutes remaining
    score = est_minutes

    # Age bonus (prevents starvation) — 2 points per hour waiting
    score -= min(age_hours * 2, 200)

    # Deadline urgency — ramps up as due date approaches
    score += deadline_bonus

    # Admin-priority — project-level tag set by admin, overrides everything
    if is_admin_priority:
        score -= 50000  # always runs before everything else

    # Explicit next-up priority — used when the operator wants one queued
    # project to start as soon as the current handoff clears, without turning
    # it into a permanent admin-priority project.
    if is_next_up:
        score -= 20000

    # Critical priority — admin-marked tickets get massive boost
    if is_critical:
        score -= 10000  # always runs first

    # Almost done bonus — if under 15 estimated minutes, big boost
    if 0 < est_minutes <= 15:
        score -= 30

    # No remaining work but project is active = new project needing tickets
    if remaining == 0 and total == 0:
        score = -100  # brand new project, prioritize it
        if is_admin_priority:
            score -= 50000  # admin-priority preserved for new projects too
    elif remaining == 0:
        # Check if there are more phases to advance to
        cur_phase, tot_phases = get_phase_state(project_file)
        if cur_phase is not None and tot_phases is not None and 0 <= cur_phase < tot_phases - 1:
            # Between phases — orchestrator needs to create next-phase tickets
            score = 10  # high priority, quick orchestrator task
            if is_admin_priority:
                score -= 50000  # admin-priority preserved
        else:
            score = 9999  # truly done, nothing to do

    # Client vs platform: used as categorical sort key (not score offset)
    # Practice client (is_practice: true in config) treated as platform-priority, not client-priority
    # Path check is sufficient here — practice is the only client with is_practice: true
    is_practice = "/clients/practice/" in project_file
    is_client = "/clients/" in project_file and not is_practice

    # Admin projects get highest priority within client tier
    is_admin = "/clients/example-client/" in project_file

    return score, remaining, age_hours, est_minutes, hours_until_due, is_client, is_admin, is_critical, is_admin_priority, is_next_up


def main():
    project_files = sys.argv[1:]

    if not project_files:
        print("No project files provided.", file=sys.stderr)
        sys.exit(1)

    scored = []
    for pf in project_files:
        pf = pf.strip()
        if not pf or not os.path.isfile(pf):
            continue
        score, remaining, age, est_min, hours_due, is_client, is_admin, is_critical, is_admin_prio, is_next_up = score_project(pf)
        scored.append((score, pf, remaining, age, est_min, hours_due, is_client, is_admin, is_critical, is_admin_prio, is_next_up))

    # Sort: admin-priority first, then next-up, then critical-priority, then admin, then client, then platform
    scored.sort(key=lambda x: (not x[9], not x[10], not x[8], not x[7], not x[6], x[0]))

    # Print project files in priority order
    for score, pf, remaining, age, est_min, hours_due, is_client, is_admin, is_critical, is_admin_prio, is_next_up in scored:
        # Output format: path (for chat-native orchestration to consume)
        print(pf)
        # Debug info to stderr
        slug = os.path.basename(pf).replace(".md", "")
        due_str = f" due={hours_due:.1f}h" if hours_due is not None else ""
        print(f"  [{slug}] score={score:.0f} remaining={remaining} ~{est_min:.0f}min age={age:.1f}h{due_str}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
