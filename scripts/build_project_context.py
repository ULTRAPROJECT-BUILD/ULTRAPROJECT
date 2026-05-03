#!/usr/bin/env python3
"""
Generate stable per-project context artifacts for the orchestrator.

This script writes derived files into a `<slug>.derived/` sibling folder next
to the project markdown file:

- `<slug>.derived/current-context.md` — human/agent-readable "what matters now"
- `<slug>.derived/artifact-index.yaml` — machine-readable authoritative pointers
- `<slug>.derived/status.md` — sleek at-a-glance status view (Obsidian/GH preview friendly)

These files are derived views only. The canonical source of truth remains the
project file, tickets, plans, briefs, and snapshot reports. The `<slug>.derived/`
folder is created on first write and is safe to wipe and rebuild at any time.
See vault/SCHEMA.md → "Project Derived Context" for the layout contract.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_ticket_evidence import parse_frontmatter_map
from resolve_briefs import build_report as build_brief_report

TICKET_ID_RE = re.compile(r"\bT-\d+\b", re.IGNORECASE)
PHASE_HEADER_RE = re.compile(r"^###\s+Phase\s+(\d+):\s*(.+?)\s*$")
CHECKPOINT_RE = re.compile(r"^- (?P<timestamp>.*?): ORCH-CHECKPOINT: (?P<summary>.+)$", re.MULTILINE)
CURRENT_WAVE_RE = re.compile(r"^Current wave:\s*(.+?)\s*$", re.MULTILINE)
FRONTMATTER_TS_KEYS = ("captured", "updated", "completed", "created")
BULLET_FIELD_RE = re.compile(r"^- \*\*(.+?):\*\*\s*(.+?)\s*$")
ACTIVE_ASSUMPTION_STATUSES = {"open", "validating"}
ABS_PATH_RE = re.compile(r"(/(?:Users|Applications|opt|private|var|Volumes|tmp)[^\s`\"'()<>\]]+)")
FILE_SUFFIX_HINTS = {".md", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".mp4", ".mov", ".pdf"}
CODE_MARKER_FILES = (
    "package.json",
    "pnpm-workspace.yaml",
    "turbo.json",
    "tsconfig.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
)
PROJECT_CODE_STATE_FILE = SCRIPT_DIR.parent / "data" / "project_code_index_state.json"

REVIEW_KIND_RULES: list[tuple[str, str]] = [
    ("delivery-review", "Delivery Review"),
    ("delivery-gate", "Delivery Gate"),
    ("credibility-gate", "Credibility Gate"),
    ("visual-gate", "Visual Gate"),
    ("artifact-polish-review", "Artifact Polish Review"),
    ("polish-gate", "Polish Gate"),
    ("phase-gate", "Phase Gate"),
    ("phase gate", "Phase Gate"),
]
AMENDMENT_CLOSED_STATUSES = {"applied", "resolved", "superseded", "closed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-file", required=True, help="Project markdown path.")
    parser.add_argument("--project-plan", help="Optional explicit project plan path.")
    parser.add_argument("--context-out", help="Optional explicit current-context output path.")
    parser.add_argument("--index-out", help="Optional explicit artifact-index output path.")
    parser.add_argument("--status-out", help="Optional explicit status.md output path.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S %Z %z")


def parse_timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)", text)
    if not match:
        return None
    try:
        return datetime.fromisoformat(match.group(1))
    except ValueError:
        return None


def phase_display_number(current_phase: Any, total_phases: Any) -> Any:
    try:
        current = int(current_phase)
        total = int(total_phases)
    except (TypeError, ValueError):
        return current_phase
    if total > 0 and 0 <= current < total:
        return current + 1
    return current


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip(), parts[2].lstrip("\n")


def extract_section(body: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in body:
        return ""
    section = body.split(marker, 1)[1]
    matches = list(re.finditer(r"^##\s+.+$", section, flags=re.MULTILINE))
    if matches:
        return section[: matches[0].start()].strip()
    return section.strip()


def parse_labeled_bullets(section_text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in section_text.splitlines():
        match = BULLET_FIELD_RE.match(raw_line.strip())
        if not match:
            continue
        parsed[match.group(1).strip()] = match.group(2).strip()
    return parsed


def relative_to_platform(path: Path, platform_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(platform_root.resolve()))
    except ValueError:
        return str(path.resolve())


def derived_dir(project_file: Path) -> Path:
    """Sibling folder that holds all derived/regenerable project artifacts.

    See vault/SCHEMA.md → "Project Derived Context" for the layout contract.
    """
    return project_file.parent / f"{project_file.stem}.derived"


def default_context_path(project_file: Path) -> Path:
    return derived_dir(project_file) / "current-context.md"


def default_index_path(project_file: Path) -> Path:
    return derived_dir(project_file) / "artifact-index.yaml"


def default_image_index_path(project_file: Path) -> Path:
    return derived_dir(project_file) / "image-evidence-index.yaml"


def default_video_index_path(project_file: Path) -> Path:
    return derived_dir(project_file) / "video-evidence-index.yaml"


def default_status_path(project_file: Path) -> Path:
    return derived_dir(project_file) / "status.md"


def load_project_code_state() -> dict[str, Any]:
    try:
        data = json.loads(PROJECT_CODE_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"workspaces": {}}
    if not isinstance(data, dict):
        return {"workspaces": {}}
    workspaces = data.get("workspaces")
    if not isinstance(workspaces, dict):
        data["workspaces"] = {}
    return data


def frontmatter_project_slug(path: Path) -> str:
    data = parse_frontmatter_map(path)
    return str(data.get("project", "")).strip().strip('"')


def path_matches_project(path: Path, project: str) -> bool:
    frontmatter_project = frontmatter_project_slug(path)
    if frontmatter_project:
        return frontmatter_project == project
    stem = path.stem
    return stem.endswith(f"-{project}") or stem == project


def discover_project_layout(project_file: Path) -> dict[str, Any]:
    resolved = project_file.resolve()
    parts = resolved.parts
    if "vault" not in parts:
        raise ValueError(f"Project file must live under a vault path: {project_file}")

    vault_idx = parts.index("vault")
    platform_root = Path(*parts[:vault_idx]) if vault_idx > 0 else Path("/")
    vault_root = platform_root / "vault"
    try:
        rel_parts = resolved.relative_to(vault_root).parts
    except ValueError as exc:
        raise ValueError(f"Project file must live under {vault_root}: {project_file}") from exc

    if len(rel_parts) >= 2 and rel_parts[0] == "projects":
        slug = Path(rel_parts[-1]).stem
        return {
            "scope": "platform",
            "project": slug,
            "client": "_platform",
            "platform_root": platform_root,
            "vault_root": vault_root,
            "client_root": vault_root,
            "project_file": resolved,
            "projects_dir": vault_root / "projects",
            "tickets_dir": vault_root / "tickets",
            "snapshots_dir": vault_root / "snapshots",
            "decisions_dir": vault_root / "decisions",
            "lessons_dir": vault_root / "lessons",
            "deliverables_root": platform_root / "deliverables",
        }

    if len(rel_parts) >= 4 and rel_parts[0] == "clients" and rel_parts[2] == "projects":
        client = rel_parts[1]
        slug = Path(rel_parts[-1]).stem
        client_root = vault_root / "clients" / client
        return {
            "scope": "client",
            "project": slug,
            "client": client,
            "platform_root": platform_root,
            "vault_root": vault_root,
            "client_root": client_root,
            "project_file": resolved,
            "projects_dir": client_root / "projects",
            "tickets_dir": client_root / "tickets",
            "snapshots_dir": client_root / "snapshots",
            "decisions_dir": client_root / "decisions",
            "lessons_dir": client_root / "lessons",
            "deliverables_root": client_root / "deliverables",
        }

    raise ValueError(f"Unsupported project file layout: {project_file}")


def read_project_body(project_file: Path) -> tuple[dict[str, Any], str]:
    text = project_file.read_text(encoding="utf-8")
    _, body = split_frontmatter(text)
    return parse_frontmatter_map(project_file), body


def find_latest_checkpoint(project_body: str) -> dict[str, str] | None:
    matches = list(CHECKPOINT_RE.finditer(project_body))
    if not matches:
        return None
    latest = matches[-1]
    return {
        "timestamp": latest.group("timestamp").strip(),
        "summary": latest.group("summary").strip(),
    }


def find_current_wave(project_body: str) -> str | None:
    match = CURRENT_WAVE_RE.search(project_body)
    if not match:
        return None
    return match.group(1).strip()


def choose_latest_path(paths: list[Path]) -> Path | None:
    if not paths:
        return None
    ranked = []
    for path in paths:
        data = parse_frontmatter_map(path)
        candidates = [parse_timestamp(data.get(key)) for key in FRONTMATTER_TS_KEYS]
        candidates = [candidate for candidate in candidates if candidate is not None]
        ts = max(candidates, default=None)
        ranked.append((ts or datetime.fromtimestamp(path.stat().st_mtime), path))
    ranked.sort(key=lambda item: (item[0], str(item[1])))
    return ranked[-1][1]


def latest_project_snapshot(layout: dict[str, Any], project: str, pattern: str) -> Path | None:
    snapshots_dir = Path(layout["snapshots_dir"])
    return choose_latest_path(
        [
            path
            for path in sorted(snapshots_dir.glob(pattern))
            if path_matches_project(path, project)
        ]
    )


def find_latest_project_plan(layout: dict[str, Any], explicit_plan: Path | None = None) -> Path | None:
    if explicit_plan and explicit_plan.exists():
        return explicit_plan.resolve()
    slug = layout["project"]
    snapshots_dir = Path(layout["snapshots_dir"])
    return choose_latest_path(sorted(snapshots_dir.glob(f"*-project-plan-{slug}.md")))


def parse_phase_block(plan_path: Path, phase_number: int | None) -> dict[str, Any] | None:
    if phase_number is None:
        return None
    lines = plan_path.read_text(encoding="utf-8").splitlines()
    current_phase: int | None = None
    current_title = ""
    phase_lines: list[str] = []
    for line in lines:
        match = PHASE_HEADER_RE.match(line.strip())
        if match:
            if current_phase == phase_number:
                break
            current_phase = int(match.group(1))
            current_title = match.group(2).strip()
            phase_lines = []
            continue
        if current_phase == phase_number:
            phase_lines.append(line)
    if current_phase != phase_number:
        return None

    goal = ""
    exit_criteria: list[str] = []
    in_exit = False
    for raw in phase_lines:
        stripped = raw.strip()
        if stripped.startswith("**Goal:**"):
            goal = stripped.split("**Goal:**", 1)[1].strip()
        if stripped == "**Exit criteria:**":
            in_exit = True
            continue
        if in_exit and stripped.startswith("**") and stripped != "**Exit criteria:**":
            in_exit = False
        if in_exit and stripped.startswith("-"):
            exit_criteria.append(stripped[1:].strip())

    return {
        "phase": phase_number,
        "title": current_title,
        "goal": goal,
        "exit_criteria": exit_criteria,
    }


def infer_phase_display_number(plan_path: Path | None, current_phase: Any, total_phases: Any) -> Any:
    if not plan_path or not plan_path.exists():
        return phase_display_number(current_phase, total_phases)
    phase_numbers = []
    for raw_line in plan_path.read_text(encoding="utf-8").splitlines():
        match = PHASE_HEADER_RE.match(raw_line.strip())
        if match:
            phase_numbers.append(int(match.group(1)))
    try:
        current = int(current_phase)
    except (TypeError, ValueError):
        return current_phase
    if phase_numbers and min(phase_numbers) == 0:
        return phase_display_number(current, total_phases)
    return current


def parse_markdown_table(body: str, heading: str) -> list[dict[str, str]]:
    marker = f"## {heading}"
    if marker not in body:
        return []
    section = extract_section(body, heading)
    lines = section.splitlines()
    table_lines: list[str] = []
    started = False
    for raw in lines:
        line = raw.rstrip()
        if not line and started:
            break
        if line.startswith("|"):
            started = True
            table_lines.append(line)
        elif started:
            break
    if len(table_lines) < 2:
        return []
    headers = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for raw in table_lines[2:]:
        cells = [cell.strip() for cell in raw.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append({headers[idx]: cells[idx] for idx in range(len(headers))})
    return rows


def collect_tickets(layout: dict[str, Any], project: str) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    for path in sorted(Path(layout["tickets_dir"]).glob("T-*.md")):
        data = parse_frontmatter_map(path)
        if str(data.get("project", "")).strip().strip('"') != project:
            continue
        blocked_by = data.get("blocked_by", [])
        if isinstance(blocked_by, str):
            blocked_by = [item.strip().strip('"') for item in blocked_by.strip("[]").split(",") if item.strip()]
        ticket_match = TICKET_ID_RE.search(path.stem.upper())
        tickets.append(
            {
                "id": str(data.get("id") or "").strip() or (ticket_match.group(0) if ticket_match else ""),
                "title": str(data.get("title", "")).strip().strip('"'),
                "status": str(data.get("status", "")).strip().lower(),
                "created": str(data.get("created", "")).strip(),
                "updated": str(data.get("updated", "")).strip(),
                "completed": str(data.get("completed", "")).strip(),
                "blocked_by": blocked_by,
                "path": path.resolve(),
            }
        )
    return tickets


def sort_tickets_by_timestamp(tickets: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(
        tickets,
        key=lambda ticket: (
            parse_timestamp(ticket.get(key)) or parse_timestamp(ticket.get("updated")) or datetime.min,
            ticket.get("id", ""),
        ),
        reverse=True,
    )


def collect_project_docs(directory: Path, project: str) -> list[Path]:
    if not directory.exists():
        return []
    matches: list[Path] = []
    for path in sorted(directory.glob("*.md")):
        data = parse_frontmatter_map(path)
        if str(data.get("project", "")).strip().strip('"') == project:
            matches.append(path.resolve())
    return matches


def classify_review(path: Path) -> tuple[str, str] | None:
    data = parse_frontmatter_map(path)
    sig = " ".join(
        [
            str(data.get("review_type", "")),
            str(data.get("subtype", "")),
            str(data.get("title", "")),
            path.stem,
        ]
    ).lower()
    for needle, label in REVIEW_KIND_RULES:
        if needle in sig:
            return needle, label
    if "phase-" in path.stem and "-gate" in path.stem:
        return "phase-gate", "Phase Gate"
    return None


def collect_reviews(layout: dict[str, Any], project: str, platform_root: Path) -> dict[str, Any]:
    snapshots_dir = Path(layout["snapshots_dir"])
    review_entries: list[dict[str, Any]] = []
    for path in sorted(snapshots_dir.glob(f"*{project}*.md")):
        if not path_matches_project(path, project):
            continue
        review_meta = classify_review(path)
        if not review_meta:
            continue
        data = parse_frontmatter_map(path)
        candidates = [parse_timestamp(data.get(key)) for key in FRONTMATTER_TS_KEYS]
        candidates = [candidate for candidate in candidates if candidate is not None]
        ts = max(candidates, default=None) or datetime.fromtimestamp(path.stat().st_mtime)
        kind, label = review_meta
        review_entries.append(
            {
                "kind": kind,
                "kind_label": label,
                "path": relative_to_platform(path, platform_root),
                "captured": ts.isoformat(timespec="seconds"),
                "grade": str(data.get("grade") or data.get("overall_grade") or "").strip().strip('"'),
                "verdict": str(data.get("verdict", "")).strip().strip('"'),
                "title": str(data.get("title", "")).strip().strip('"'),
            }
        )

    latest_by_kind: dict[str, dict[str, Any]] = {}
    for entry in review_entries:
        current = latest_by_kind.get(entry["kind"])
        if current is None or entry["captured"] > current["captured"]:
            latest_by_kind[entry["kind"]] = entry

    current_review = None
    if review_entries:
        current_review = sorted(review_entries, key=lambda entry: (entry["captured"], entry["kind_label"]))[-1]

    return {
        "current_review": current_review,
        "latest_by_kind": latest_by_kind,
    }


def collect_amendments(layout: dict[str, Any], project: str, platform_root: Path) -> dict[str, Any]:
    snapshots_dir = Path(layout["snapshots_dir"])
    entries: list[dict[str, Any]] = []
    for path in sorted(snapshots_dir.glob(f"*{project}*.md")):
        if not path_matches_project(path, project):
            continue
        data = parse_frontmatter_map(path)
        subtype = str(data.get("subtype", "")).strip().lower()
        if subtype != "project-amendment":
            continue
        candidates = [parse_timestamp(data.get(key)) for key in FRONTMATTER_TS_KEYS]
        candidates = [candidate for candidate in candidates if candidate is not None]
        ts = max(candidates, default=None) or datetime.fromtimestamp(path.stat().st_mtime)
        entries.append(
            {
                "path": relative_to_platform(path, platform_root),
                "captured": ts.isoformat(timespec="seconds"),
                "status": str(data.get("status", "")).strip().lower() or "pending",
                "classification": str(data.get("classification", "")).strip(),
                "apply_mode": str(data.get("apply_mode", "")).strip(),
                "summary": str(data.get("request_summary", "")).strip(),
                "title": str(data.get("title", "")).strip().strip('"'),
            }
        )
    entries.sort(key=lambda item: (item["captured"], item["path"]), reverse=True)
    pending = [entry for entry in entries if entry["status"] not in AMENDMENT_CLOSED_STATUSES]
    latest = entries[0] if entries else None
    return {
        "latest": latest,
        "pending": pending,
        "recent": entries[:5],
    }


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in paths:
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def load_image_evidence_summary(image_index_path: Path) -> dict[str, Any]:
    if not image_index_path.exists():
        return {"count": 0, "category_counts": {}, "images": [], "semantic_image_corpus": []}
    try:
        data = yaml.safe_load(image_index_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {"count": 0, "category_counts": {}, "images": [], "semantic_image_corpus": []}
    image_evidence = data.get("image_evidence") or {}
    images = image_evidence.get("images") or []
    return {
        "count": int(image_evidence.get("count") or len(images)),
        "category_counts": image_evidence.get("category_counts") or {},
        "images": images[:8],
        "semantic_image_corpus": data.get("semantic_image_corpus") or [image.get("path") for image in images if image.get("path")],
    }


def load_video_evidence_summary(video_index_path: Path) -> dict[str, Any]:
    if not video_index_path.exists():
        return {"count": 0, "category_counts": {}, "videos": [], "semantic_video_corpus": []}
    try:
        data = yaml.safe_load(video_index_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {"count": 0, "category_counts": {}, "videos": [], "semantic_video_corpus": []}
    video_evidence = data.get("video_evidence") or {}
    videos = video_evidence.get("videos") or []
    return {
        "count": int(video_evidence.get("count") or len(videos)),
        "category_counts": video_evidence.get("category_counts") or {},
        "videos": videos[:6],
        "semantic_video_corpus": data.get("semantic_video_corpus") or [video.get("path") for video in videos if video.get("path")],
    }


def extract_absolute_paths(text: str) -> list[tuple[str, str]]:
    if not text:
        return []
    hits: list[tuple[str, str]] = []
    for match in ABS_PATH_RE.finditer(text):
        raw = match.group(1).rstrip(".,:;)]}")
        start = max(0, match.start() - 120)
        end = min(len(text), match.end() + 120)
        snippet = text[start:end]
        hits.append((raw, snippet))
    return hits


def likely_code_workspace_candidate(raw_path: str) -> bool:
    if "..." in raw_path:
        return False
    candidate = Path(raw_path)
    if candidate.suffix.lower() in FILE_SUFFIX_HINTS:
        return False
    return True


def infer_workspace_role(snippet: str) -> str:
    text = snippet.lower()
    if any(token in text for token in ("dependency", "framework", "framework at", "framework repo", "depends on", "verified against", "against real framework")):
        return "dependency"
    if any(token in text for token in ("standalone web application", "web application at", "control platform", "monorepo scaffolded at", "app root", "workspace root", "application at")):
        return "primary"
    return "supporting"


def role_priority(role: str) -> int:
    return {"primary": 3, "dependency": 2, "supporting": 1}.get(role, 0)


def infer_workspace_languages(root: Path) -> list[str]:
    languages: list[str] = []
    if (root / "package.json").exists() or (root / "pnpm-workspace.yaml").exists() or (root / "turbo.json").exists() or (root / "tsconfig.json").exists():
        languages.extend(["TypeScript", "JavaScript"])
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        languages.append("Python")
    if (root / "Cargo.toml").exists():
        languages.append("Rust")
    if (root / "go.mod").exists():
        languages.append("Go")
    return languages


def run_command(command: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=10, check=False)
    except Exception:
        return False, ""
    if result.returncode != 0:
        return False, ""
    return True, (result.stdout or "").strip()


def discover_git_root(path: Path) -> Path | None:
    probe = path if path.is_dir() else path.parent
    if not probe.exists():
        return None
    ok, output = run_command(["git", "rev-parse", "--show-toplevel"], probe)
    if not ok or not output:
        return None
    return Path(output).expanduser().resolve()


def workspace_state_key(path: Path, platform_root: Path) -> str:
    return relative_to_platform(path, platform_root)


def summarize_code_workspaces(
    project_frontmatter: dict[str, Any],
    project_body: str,
    plan_body: str,
    phase_block: dict[str, Any] | None,
    platform_root: Path,
    code_state: dict[str, Any],
) -> list[dict[str, Any]]:
    source_texts = [
        ("project-goal", str(project_frontmatter.get("goal", "")).strip()),
        ("project-body", project_body),
        ("plan-body", plan_body),
    ]
    if phase_block:
        source_texts.append(("phase-goal", str(phase_block.get("goal", "")).strip()))
        source_texts.append(("phase-exit", "\n".join(phase_block.get("exit_criteria") or [])))

    candidates: dict[str, dict[str, Any]] = {}
    state_workspaces = code_state.get("workspaces") if isinstance(code_state, dict) else {}
    state_workspaces = state_workspaces if isinstance(state_workspaces, dict) else {}

    for source_name, text in source_texts:
        for idx, (raw_path, snippet) in enumerate(extract_absolute_paths(text)):
            if not likely_code_workspace_candidate(raw_path):
                continue
            normalized = Path(raw_path).expanduser()
            key = str(normalized)
            role = infer_workspace_role(snippet)
            if source_name == "project-goal" and idx == 0:
                role = "primary"
            existing = candidates.get(key)
            if existing is None:
                candidates[key] = {
                    "declared_path": raw_path,
                    "source": source_name,
                    "role": role,
                }
            elif role_priority(role) > role_priority(existing.get("role", "")):
                existing["role"] = role

    workspaces: list[dict[str, Any]] = []
    primary_assigned = False
    for item in candidates.values():
        declared = Path(item["declared_path"]).expanduser()
        exists = declared.exists()
        git_root = discover_git_root(declared)
        root = git_root or declared
        role = item["role"]
        if role == "supporting" and item.get("source") == "project-goal" and not primary_assigned:
            role = "primary"
        if role == "primary":
            primary_assigned = True
        branch = ""
        head = ""
        dirty = False
        if git_root:
            ok_branch, branch_output = run_command(["git", "branch", "--show-current"], git_root)
            if ok_branch:
                branch = branch_output
            ok_head, head_output = run_command(["git", "rev-parse", "HEAD"], git_root)
            if ok_head:
                head = head_output
            ok_dirty, dirty_output = run_command(["git", "status", "--porcelain"], git_root)
            if ok_dirty:
                dirty = bool(dirty_output)
        markers = [marker for marker in CODE_MARKER_FILES if (root / marker).exists()] if root.exists() else []
        workspace_key = workspace_state_key(root, platform_root)
        state_entry = state_workspaces.get(workspace_key, {}) if isinstance(state_workspaces, dict) else {}
        state_entry = state_entry if isinstance(state_entry, dict) else {}
        last_status = str(state_entry.get("last_status", "")).strip()
        last_head = str(state_entry.get("head", "")).strip()
        last_updated = str(state_entry.get("updated_at", "")).strip()
        gitnexus_ready = bool(git_root and last_status == "refreshed" and head and last_head == head)
        gitnexus_stale = bool(
            git_root
            and (root / ".gitnexus").exists()
            and last_status == "refreshed"
            and head
            and last_head
            and last_head != head
        )
        workspaces.append(
            {
                "root": str(root),
                "key": workspace_key,
                "declared_path": item["declared_path"],
                "source": item["source"],
                "role": role,
                "exists": exists,
                "git_repo": bool(git_root),
                "branch": branch,
                "head": head,
                "dirty": dirty,
                "markers": markers,
                "languages": infer_workspace_languages(root) if root.exists() else [],
                "gitnexus_enabled": role != "dependency",
                "gitnexus_index_present": (root / ".gitnexus").exists() if root.exists() else False,
                "gitnexus_last_status": last_status,
                "gitnexus_last_updated": last_updated,
                "gitnexus_last_head": last_head,
                "gitnexus_ready": gitnexus_ready,
                "gitnexus_stale": gitnexus_stale,
            }
        )

    workspaces.sort(key=lambda row: (-role_priority(str(row.get("role", ""))), str(row.get("root", ""))))
    return workspaces


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    project_file = Path(args.project_file).expanduser().resolve()
    layout = discover_project_layout(project_file)
    platform_root = Path(layout["platform_root"])
    project = layout["project"]
    project_frontmatter, project_body = read_project_body(project_file)
    latest_checkpoint = find_latest_checkpoint(project_body)
    current_wave = find_current_wave(project_body)

    plan_path = find_latest_project_plan(layout, Path(args.project_plan).expanduser().resolve() if args.project_plan else None)
    plan_data = parse_frontmatter_map(plan_path) if plan_path and plan_path.exists() else {}
    current_phase = int(plan_data.get("current_phase")) if str(plan_data.get("current_phase", "")).strip() else None
    total_phases = int(plan_data.get("total_phases")) if str(plan_data.get("total_phases", "")).strip() else None
    current_phase_display = infer_phase_display_number(plan_path, current_phase, total_phases)
    phase_block = parse_phase_block(plan_path, current_phase) if plan_path else None
    plan_body = split_frontmatter(plan_path.read_text(encoding="utf-8"))[1] if plan_path and plan_path.exists() else ""
    artifact_manifest = parse_markdown_table(plan_body, "Artifact Manifest") if plan_body else []
    goal_contract_section = extract_section(plan_body, "Goal Contract") if plan_body else ""
    goal_contract_fields = parse_labeled_bullets(goal_contract_section) if goal_contract_section else {}
    goal_workstreams = parse_markdown_table(plan_body, "Goal Contract") if plan_body else []
    assumption_register = parse_markdown_table(plan_body, "Assumption Register") if plan_body else []
    active_assumptions = [
        row
        for row in assumption_register
        if str(row.get("Status", "")).strip().lower() in ACTIVE_ASSUMPTION_STATUSES
    ]

    tickets = collect_tickets(layout, project)
    active_tickets = [ticket for ticket in tickets if ticket["status"] and ticket["status"] != "closed"]
    blocked_tickets = [ticket for ticket in active_tickets if ticket["status"] in {"blocked", "waiting"}]
    recent_closed_tickets = sort_tickets_by_timestamp([ticket for ticket in tickets if ticket["status"] == "closed"], "completed")[:5]

    brief_report = build_brief_report(
        argparse.Namespace(
            project=project,
            project_file=str(project_file),
            project_plan=str(plan_path) if plan_path else None,
            phase=current_phase,
            wave=current_wave,
            ticket_id=None,
            ticket_path=None,
            search_root=[str(layout["snapshots_dir"])],
            json_out=None,
            markdown_out=None,
        )
    )

    decisions = collect_project_docs(Path(layout["decisions_dir"]), project)
    lessons = collect_project_docs(Path(layout["lessons_dir"]), project)
    review_data = collect_reviews(layout, project, platform_root)
    amendment_data = collect_amendments(layout, project, platform_root)

    latest_review_pack = choose_latest_path(
        [
            path
            for path in sorted(Path(layout["snapshots_dir"]).glob(f"*-review-pack*{project}*.md"))
            if path_matches_project(path, project)
        ]
    )
    latest_drift_report = latest_project_snapshot(layout, project, f"*-drift-detection*{project}*.md")
    latest_rehearsal_packet = latest_project_snapshot(layout, project, f"*-rehearsal*{project}*.md")

    context_out_arg = getattr(args, "context_out", None)
    index_out_arg = getattr(args, "index_out", None)
    context_out = Path(context_out_arg).expanduser().resolve() if context_out_arg else default_context_path(project_file)
    index_out = Path(index_out_arg).expanduser().resolve() if index_out_arg else default_index_path(project_file)
    image_index_path = default_image_index_path(project_file)
    video_index_path = default_video_index_path(project_file)
    image_evidence = load_image_evidence_summary(image_index_path)
    video_evidence = load_video_evidence_summary(video_index_path)
    code_state = load_project_code_state()
    code_workspaces = summarize_code_workspaces(
        project_frontmatter,
        project_body,
        plan_body,
        phase_block,
        platform_root,
        code_state,
    )

    authoritative_files = unique_paths(
        [
            relative_to_platform(project_file, platform_root),
            relative_to_platform(plan_path, platform_root) if plan_path else "",
            *(entry["path"] for entry in brief_report.get("ordered_briefs", [])),
            relative_to_platform(latest_review_pack, platform_root) if latest_review_pack else "",
            review_data["current_review"]["path"] if review_data.get("current_review") else "",
        ]
    )

    semantic_corpus = unique_paths(
        authoritative_files
        + [relative_to_platform(path, platform_root) for path in decisions]
        + [relative_to_platform(path, platform_root) for path in lessons]
        + [relative_to_platform(Path(ticket["path"]), platform_root) for ticket in active_tickets]
        + [relative_to_platform(Path(ticket["path"]), platform_root) for ticket in recent_closed_tickets]
        + [entry["path"] for entry in amendment_data.get("recent", [])]
        + ([relative_to_platform(latest_drift_report, platform_root)] if latest_drift_report else [])
        + ([relative_to_platform(latest_rehearsal_packet, platform_root)] if latest_rehearsal_packet else [])
    )

    return {
        "generated_at": now(),
        "scope": layout["scope"],
        "client": layout["client"],
        "project": project,
        "title": str(project_frontmatter.get("title", project)).strip().strip('"'),
        "goal": str(project_frontmatter.get("goal", "")).strip().strip('"'),
        "status": str(project_frontmatter.get("status", "")).strip(),
        "current_phase": current_phase,
        "current_phase_display": current_phase_display,
        "total_phases": total_phases,
        "current_phase_title": phase_block["title"] if phase_block else "",
        "current_phase_goal": phase_block["goal"] if phase_block else "",
        "current_phase_exit_criteria": phase_block["exit_criteria"] if phase_block else [],
        "current_wave": current_wave or "",
        "latest_checkpoint": latest_checkpoint,
        "goal_contract": {
            "fields": goal_contract_fields,
            "workstreams": goal_workstreams,
        },
        "assumptions": {
            "all": assumption_register,
            "active": active_assumptions,
        },
        "paths": {
            "project_file": relative_to_platform(project_file, platform_root),
            "project_plan": relative_to_platform(plan_path, platform_root) if plan_path else "",
            "tickets_dir": relative_to_platform(Path(layout["tickets_dir"]), platform_root),
            "snapshots_dir": relative_to_platform(Path(layout["snapshots_dir"]), platform_root),
            "decisions_dir": relative_to_platform(Path(layout["decisions_dir"]), platform_root),
            "lessons_dir": relative_to_platform(Path(layout["lessons_dir"]), platform_root),
            "deliverables_root": relative_to_platform(Path(layout["deliverables_root"]), platform_root),
            "current_context": relative_to_platform(context_out, platform_root),
            "artifact_index": relative_to_platform(index_out, platform_root),
            "image_evidence_index": relative_to_platform(image_index_path, platform_root),
            "video_evidence_index": relative_to_platform(video_index_path, platform_root),
        },
        "briefs": {
            "ordered": brief_report.get("ordered_briefs", []),
            "issues": brief_report.get("issues", []),
        },
        "reviews": review_data,
        "amendments": amendment_data,
        "latest_review_pack": relative_to_platform(latest_review_pack, platform_root) if latest_review_pack else "",
        "latest_amendment": amendment_data["latest"]["path"] if amendment_data.get("latest") else "",
        "latest_drift_report": relative_to_platform(latest_drift_report, platform_root) if latest_drift_report else "",
        "latest_rehearsal_packet": relative_to_platform(latest_rehearsal_packet, platform_root) if latest_rehearsal_packet else "",
        "artifact_manifest": artifact_manifest,
        "tickets": {
            "active": [
                {
                    "id": ticket["id"],
                    "title": ticket["title"],
                    "status": ticket["status"],
                    "blocked_by": ticket["blocked_by"],
                    "path": relative_to_platform(Path(ticket["path"]), platform_root),
                }
                for ticket in sort_tickets_by_timestamp(active_tickets, "updated")
            ],
            "blocked": [
                {
                    "id": ticket["id"],
                    "title": ticket["title"],
                    "status": ticket["status"],
                    "blocked_by": ticket["blocked_by"],
                    "path": relative_to_platform(Path(ticket["path"]), platform_root),
                }
                for ticket in sort_tickets_by_timestamp(blocked_tickets, "updated")
            ],
            "recent_closed": [
                {
                    "id": ticket["id"],
                    "title": ticket["title"],
                    "completed": ticket["completed"],
                    "path": relative_to_platform(Path(ticket["path"]), platform_root),
                }
                for ticket in recent_closed_tickets
            ],
        },
        "decisions": [relative_to_platform(path, platform_root) for path in decisions],
        "lessons": [relative_to_platform(path, platform_root) for path in lessons],
        "authoritative_files": authoritative_files,
        "semantic_corpus": semantic_corpus,
        "image_evidence": image_evidence,
        "video_evidence": video_evidence,
        "code_workspaces": code_workspaces,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Current Context — {report['title']}",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Scope: {report['scope']}",
        f"- Client: {report['client']}",
        f"- Project: `{report['project']}`",
        f"- Status: `{report['status'] or 'unknown'}`",
    ]
    if report.get("current_phase") is not None:
        phase_label = f"Phase {report.get('current_phase_display', report['current_phase'])}"
        if report.get("total_phases"):
            phase_label += f"/{report['total_phases']}"
        if report.get("current_phase_title"):
            phase_label += f" — {report['current_phase_title']}"
        lines.append(f"- Current phase: {phase_label}")
    if report.get("current_wave"):
        lines.append(f"- Current wave: {report['current_wave']}")
    current_review = report.get("reviews", {}).get("current_review")
    if current_review:
        review_label = current_review["kind_label"]
        if current_review.get("grade"):
            review_label += f" ({current_review['grade']})"
        lines.append(f"- Current review surface: {review_label}")
    if report.get("latest_checkpoint"):
        checkpoint = report["latest_checkpoint"]
        lines.append(f"- Latest checkpoint: {checkpoint['timestamp']} — {checkpoint['summary']}")
    lines.extend(["", "## Goal", "", report.get("goal") or "_No goal recorded._", ""])

    goal_contract_fields = report.get("goal_contract", {}).get("fields", {})
    if goal_contract_fields:
        lines.extend(["## Goal Contract", ""])
        for label in (
            "Rigor tier",
            "Mission",
            "Primary evaluator",
            "Mission success",
            "Primary success metrics",
            "Primary risks",
            "Proof shape",
        ):
            value = goal_contract_fields.get(label, "").strip()
            if value:
                lines.append(f"- {label}: {value}")
        human_owned = goal_contract_fields.get("Human-owned decisions", "").strip()
        agent_owned = goal_contract_fields.get("Agent-owned execution", "").strip()
        if human_owned:
            lines.append(f"- Human-owned decisions: {human_owned}")
        if agent_owned:
            lines.append(f"- Agent-owned execution: {agent_owned}")
        goal_workstreams = report.get("goal_contract", {}).get("workstreams", [])
        if goal_workstreams:
            workstream_labels = [
                row.get("Goal / Workstream", "").strip()
                for row in goal_workstreams[:6]
                if row.get("Goal / Workstream", "").strip()
            ]
            if workstream_labels:
                lines.append(f"- Goal workstreams: {', '.join(workstream_labels)}")
        lines.append("")

    if report.get("current_phase_goal") or report.get("current_phase_exit_criteria"):
        lines.extend(["## Current Phase", ""])
        if report.get("current_phase_goal"):
            lines.append(f"- Goal: {report['current_phase_goal']}")
        if report.get("current_phase_exit_criteria"):
            lines.append("- Exit criteria:")
            for item in report["current_phase_exit_criteria"]:
                lines.append(f"  - {item}")
        lines.append("")

    lines.extend(["## Pending Amendments", ""])
    pending_amendments = report.get("amendments", {}).get("pending", [])
    if not pending_amendments:
        lines.append("- No pending project amendments.")
    else:
        for amendment in pending_amendments[:5]:
            summary = amendment.get("summary") or amendment.get("title") or amendment.get("path")
            lines.append(
                f"- `{amendment.get('path', '')}` [{amendment.get('classification') or 'amendment'} | {amendment.get('status', 'pending')}] {summary}"
            )
    lines.append("")

    lines.extend(["## Active Tickets", ""])
    active_tickets = report.get("tickets", {}).get("active", [])
    if not active_tickets:
        lines.append("- No active tickets.")
    else:
        for ticket in active_tickets[:10]:
            blocker_text = ""
            if ticket.get("blocked_by"):
                blocker_text = f" | blocked_by: {', '.join(ticket['blocked_by'])}"
            lines.append(f"- `{ticket['id']}` [{ticket['status']}] {ticket['title']}{blocker_text}")
    lines.append("")

    lines.extend(["## Current Blockers", ""])
    blocked = report.get("tickets", {}).get("blocked", [])
    if not blocked:
        lines.append("- No explicitly blocked/waiting tickets.")
    else:
        for ticket in blocked:
            blockers = ", ".join(ticket.get("blocked_by") or []) or "none listed"
            lines.append(f"- `{ticket['id']}` [{ticket['status']}] {ticket['title']} — blocked_by: {blockers}")
    lines.append("")

    lines.extend(["## Active Assumptions", ""])
    active_assumptions = report.get("assumptions", {}).get("active", [])
    if not active_assumptions:
        lines.append("- No unresolved assumptions recorded.")
    else:
        for row in active_assumptions[:8]:
            assumption = row.get("Assumption", "").strip() or row.get("ID", "").strip() or "Unnamed assumption"
            status = row.get("Status", "").strip() or "unknown"
            target = row.get("Target Phase/Gate", "").strip()
            risk = row.get("Risk", "").strip()
            suffix_parts = [part for part in (risk, target) if part]
            suffix = f" ({' | '.join(suffix_parts)})" if suffix_parts else ""
            lines.append(f"- `{row.get('ID', '?')}` [{status}] {assumption}{suffix}")
    lines.append("")

    lines.extend(["## Recent Closed Tickets", ""])
    recent_closed = report.get("tickets", {}).get("recent_closed", [])
    if not recent_closed:
        lines.append("- No recently closed tickets.")
    else:
        for ticket in recent_closed:
            completed = ticket.get("completed") or "unknown completion time"
            lines.append(f"- `{ticket['id']}` — {ticket['title']} ({completed})")
    lines.append("")

    lines.extend(["## Image Evidence", ""])
    image_evidence = report.get("image_evidence") or {}
    if not image_evidence.get("count"):
        lines.append("- No indexed image evidence yet.")
    else:
        lines.append(f"- Indexed images: {image_evidence['count']}")
        category_counts = image_evidence.get("category_counts") or {}
        if category_counts:
            summary = ", ".join(f"{key}: {value}" for key, value in category_counts.items())
            lines.append(f"- Categories: {summary}")
        for image in image_evidence.get("images", [])[:5]:
            category = image.get("category", "image")
            lines.append(f"- `{image.get('path', '')}` ({category})")
    lines.append("")

    lines.extend(["## Video Evidence", ""])
    video_evidence = report.get("video_evidence") or {}
    if not video_evidence.get("count"):
        lines.append("- No indexed video evidence yet.")
    else:
        lines.append(f"- Indexed videos: {video_evidence['count']}")
        category_counts = video_evidence.get("category_counts") or {}
        if category_counts:
            summary = ", ".join(f"{key}: {value}" for key, value in category_counts.items())
            lines.append(f"- Categories: {summary}")
        for video in video_evidence.get("videos", [])[:5]:
            category = video.get("category", "video")
            duration = video.get("duration_seconds")
            duration_suffix = f", {duration:.2f}s" if isinstance(duration, (int, float)) else ""
            lines.append(f"- `{video.get('path', '')}` ({category}{duration_suffix})")
    lines.append("")

    lines.extend(["## Code Workspaces", ""])
    code_workspaces = report.get("code_workspaces") or []
    if not code_workspaces:
        lines.append("- No code workspaces discovered yet.")
    else:
        for workspace in code_workspaces:
            role = workspace.get("role", "workspace")
            status_bits = []
            if workspace.get("exists"):
                status_bits.append("exists")
            else:
                status_bits.append("expected")
            if workspace.get("git_repo"):
                status_bits.append("git")
            if workspace.get("gitnexus_enabled"):
                if workspace.get("gitnexus_ready"):
                    status_bits.append("gitnexus-ready")
                elif workspace.get("gitnexus_stale"):
                    status_bits.append("gitnexus-stale")
                elif workspace.get("gitnexus_last_status"):
                    status_bits.append(f"gitnexus-{workspace['gitnexus_last_status']}")
                else:
                    status_bits.append("gitnexus-pending")
            elif workspace.get("git_repo"):
                status_bits.append("gitnexus-disabled")
            label = " | ".join(status_bits)
            lines.append(f"- `{workspace.get('root', '')}` [{role}] ({label})")
            if workspace.get("languages"):
                lines.append(f"  - Languages: {', '.join(workspace['languages'])}")
            if workspace.get("branch"):
                lines.append(f"  - Branch: `{workspace['branch']}`")
    lines.append("")

    lines.extend(["## Drift & Rehearsal", ""])
    if report.get("latest_amendment"):
        lines.append(f"- Latest amendment artifact: `{report['latest_amendment']}`")
    if report.get("latest_drift_report"):
        lines.append(f"- Latest drift report: `{report['latest_drift_report']}`")
    if report.get("latest_rehearsal_packet"):
        lines.append(f"- Latest rehearsal packet: `{report['latest_rehearsal_packet']}`")
    if not report.get("latest_amendment") and not report.get("latest_drift_report") and not report.get("latest_rehearsal_packet"):
        lines.append("- No drift or rehearsal artifacts yet.")
    lines.append("")

    lines.extend(["## Authoritative Files", ""])
    for path in report.get("authoritative_files", []):
        lines.append(f"- `{path}`")
    lines.append("")

    lines.extend(["## Related Decisions", ""])
    if report.get("decisions"):
        for path in report["decisions"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None linked to this project yet.")
    lines.append("")

    lines.extend(["## Related Lessons", ""])
    if report.get("lessons"):
        for path in report["lessons"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- None linked to this project yet.")
    lines.append("")

    lines.extend(
        [
            "## Semantic Corpus",
            "",
            f"- Curated file count: {len(report.get('semantic_corpus', []))}",
            f"- Full machine index: `{report['paths']['artifact_index']}`",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


STATUS_ICONS: dict[str, str] = {
    "in-progress": "⏳",
    "waiting": "⏸",
    "blocked": "🚫",
    "closed": "✅",
}


def _status_with_icon(status: str) -> str:
    """Return '<icon> <status>' if a known icon exists, else just status."""
    icon = STATUS_ICONS.get(status.strip().lower())
    return f"{icon} {status}" if icon else status


def render_status_markdown(report: dict[str, Any]) -> str:
    """Sleek per-project status view, rendered identically in Obsidian / GitHub / VS Code."""
    title = (report.get("title") or report.get("project") or "").strip()
    project = report.get("project", "")
    client = report.get("client") or "_platform"
    client_display = "platform" if client == "_platform" else client
    status = (report.get("status") or "").strip() or "active"
    generated = report.get("generated_at", now())

    phase_display = report.get("current_phase_display")
    total_phases = report.get("total_phases")
    if phase_display is not None and total_phases:
        phase_token = f"{phase_display}/{total_phases}"
    elif phase_display is not None:
        phase_token = str(phase_display)
    else:
        phase_token = ""

    fm: list[str] = ["---", "type: project-status", f"project: {project}", f"client: {client}"]
    if phase_token:
        fm.append(f"phase: {phase_token}")
    fm.append(f"status: {status}")
    fm.append(f"updated: {generated}")
    fm.append("---")
    fm.append("")

    body: list[str] = [f"# {title}  ·  *{client_display}*", ""]
    goal = (report.get("goal") or "").strip()
    if goal:
        body.append(f"> {goal}")
        body.append("")

    status_bits: list[str] = []
    if phase_token:
        phase_label = f"**Phase {phase_token}**"
        if report.get("current_phase_title"):
            phase_label += f" — {report['current_phase_title']}"
        status_bits.append(phase_label)
    if report.get("current_wave"):
        status_bits.append(f"Wave: *{report['current_wave']}*")
    review = (report.get("reviews") or {}).get("current_review")
    if review:
        rl = review.get("kind_label") or "Review"
        if review.get("grade"):
            rl += f" ({review['grade']})"
        status_bits.append(f"Review: {rl}")
    if status_bits:
        body.append("  ·  ".join(status_bits))
        body.append("")

    checkpoint = report.get("latest_checkpoint")
    if checkpoint:
        ts = checkpoint.get("timestamp", "").strip()
        summary = checkpoint.get("summary", "").strip()
        if summary:
            ts_part = f" *(at {ts})*" if ts else ""
            body.append(f"_Last checkpoint:_ {summary}{ts_part}")
            body.append("")

    body.append("---")
    body.append("")
    body.append("### Active")
    body.append("")
    active = (report.get("tickets") or {}).get("active") or []
    if not active:
        body.append("_No active tickets._")
        body.append("")
    else:
        body.append("| Ticket | Title | Status |")
        body.append("| ------ | ----- | ------ |")
        for ticket in active[:12]:
            blocker = ""
            if ticket.get("blocked_by"):
                blocker = f" → {', '.join(ticket['blocked_by'])}"
            tid = ticket.get("id", "")
            ttitle = (ticket.get("title") or "").replace("|", "\\|")
            tstatus = _status_with_icon(ticket.get("status", ""))
            body.append(f"| `{tid}` | {ttitle} | {tstatus}{blocker} |")
        body.append("")

    blocked = (report.get("tickets") or {}).get("blocked") or []
    if blocked:
        body.append(f"<details><summary>Blocked ({len(blocked)})</summary>")
        body.append("")
        for ticket in blocked:
            blockers = ", ".join(ticket.get("blocked_by") or [])
            if blockers:
                suffix = f" *(blocked_by: {blockers})*"
            else:
                tstatus = ticket.get("status", "").strip()
                suffix = f" *({_status_with_icon(tstatus)})*" if tstatus else ""
            body.append(
                f"- `{ticket.get('id','')}` — {ticket.get('title','')}{suffix}"
            )
        body.append("")
        body.append("</details>")
        body.append("")

    closed = (report.get("tickets") or {}).get("recent_closed") or []
    if closed:
        body.append(f"<details><summary>Recently closed ({len(closed)})</summary>")
        body.append("")
        for ticket in closed:
            ts = (ticket.get("completed") or "").strip()
            ts_part = f" *({ts})*" if ts else ""
            body.append(f"- ✅ `{ticket.get('id','')}` — {ticket.get('title','')}{ts_part}")
        body.append("")
        body.append("</details>")
        body.append("")

    body.append("---")
    body.append(f"*Generated by build_project_context at {generated}*")

    return "\n".join(fm + body).rstrip() + "\n"


def write_outputs(
    report: dict[str, Any],
    context_path: Path,
    index_path: Path,
    status_path: Path | None = None,
) -> None:
    if status_path is None:
        status_path = index_path.parent / "status.md"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(render_markdown(report), encoding="utf-8")
    index_path.write_text(yaml.safe_dump(report, sort_keys=False, allow_unicode=False), encoding="utf-8")
    status_path.write_text(render_status_markdown(report), encoding="utf-8")


def main() -> int:
    args = parse_args()
    report = build_report(args)
    project_path = Path(args.project_file).expanduser().resolve()
    context_path = Path(args.context_out).expanduser().resolve() if args.context_out else default_context_path(project_path)
    index_path = Path(args.index_out).expanduser().resolve() if args.index_out else default_index_path(project_path)
    status_path = Path(args.status_out).expanduser().resolve() if args.status_out else default_status_path(project_path)
    write_outputs(report, context_path, index_path, status_path)
    print(f"Wrote {context_path}")
    print(f"Wrote {index_path}")
    print(f"Wrote {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
