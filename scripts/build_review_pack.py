#!/usr/bin/env python3
"""
Build a domain-agnostic review pack for clean-room artifact polish review.

The review pack is a lightweight manifest of the user/client-consumed artifact
surfaces so reviewers inspect the artifact itself rather than implementation
details or builder narration.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
ARTIFACT_REF_RE = re.compile(r"\b([A-Za-z0-9._-]+\.(?:png|jpg|jpeg|webp|gif|svg|mp4|mov|webm))\b", re.IGNORECASE)
WALKTHROUGH_NAME_RE = re.compile(r"(walkthrough|playthrough|screen[-_ ]?record(?:ing)?|demo)", re.IGNORECASE)
INTERACTIVE_WEB_KEYWORD_RE = re.compile(
    r"\b(web app|dashboard|admin panel|admin page|settings flow|settings page|"
    r"account page|interactive|multi-step|multi step|tool|workspace|portal|"
    r"console|editor|game|simulator|flow|wizard)\b",
    re.IGNORECASE,
)
STATIC_WEBSITE_KEYWORD_RE = re.compile(
    r"\b(landing page|marketing site|brochure site|portfolio|hero section|seo page|"
    r"brand site|homepage|company website)\b",
    re.IGNORECASE,
)
SKIP_DIR_NAMES = {".git", "node_modules", "dist", "build", ".next", ".nuxt", "__pycache__", "coverage", ".venv", "venv"}

CATEGORY_BY_SUFFIX = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".svg": "image",
    ".pdf": "document",
    ".md": "document",
    ".html": "document",
    ".htm": "document",
    ".pptx": "document",
    ".docx": "document",
    ".csv": "data",
    ".tsv": "data",
    ".xlsx": "data",
    ".xls": "data",
    ".json": "data",
    ".parquet": "data",
    ".mp4": "media",
    ".mov": "media",
    ".webm": "media",
    ".mp3": "media",
    ".wav": "media",
    ".m4a": "media",
    ".dmg": "application",
    ".exe": "application",
    ".apk": "application",
    ".ipa": "application",
}

PRIORITY_NAMES = {
    "README.md",
    "HANDOFF.md",
    "LIMITATIONS.md",
    "index.html",
    "demo.html",
    "report.pdf",
    "slides.pdf",
}


def read_existing_text(paths: list[Path]) -> str:
    parts = []
    for path in paths:
        if not path.exists():
            continue
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deliverables-root", required=True, help="Root of the deliverable set.")
    parser.add_argument(
        "--brief",
        action="append",
        default=[],
        help="Optional creative brief path(s). Repeat in project -> phase -> ticket order when a brief stack exists.",
    )
    parser.add_argument("--qc-report", action="append", default=[], help="Optional QC report path(s).")
    parser.add_argument("--max-files-per-category", type=int, default=12, help="Cap listed files per category.")
    parser.add_argument("--json-out", required=True, help="Where to write the review-pack JSON.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the review-pack markdown.")
    return parser.parse_args()


def walk_dirs(root: Path, max_depth: int = 5) -> list[Path]:
    discovered = []
    stack = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        discovered.append(current)
        if depth >= max_depth:
            continue
        try:
            children = sorted(current.iterdir(), key=lambda child: child.name, reverse=True)
        except OSError:
            continue
        for child in children:
            if child.is_dir() and child.name not in SKIP_DIR_NAMES:
                stack.append((child, depth + 1))
    return discovered


def unique_paths(paths: list[Path]) -> list[Path]:
    seen = set()
    unique = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return sorted(unique, key=lambda path: str(path))


def display_path(path: Path, root: Path, qc_paths: list[Path]) -> str:
    resolved = path.resolve()
    candidates = [root.resolve()]
    for qc_path in qc_paths:
        candidates.append(qc_path.parent.resolve())
    for base in candidates:
        try:
            return str(resolved.relative_to(base))
        except ValueError:
            continue
    for parent in resolved.parents:
        if parent.name in {"OneShot", "OneShot-clean"}:
            try:
                return str(resolved.relative_to(parent))
            except ValueError:
                continue
    return str(resolved)


def classify_path(path: Path) -> str:
    if path.is_dir() and path.suffix.lower() == ".app":
        return "application"
    if path.name in PRIORITY_NAMES:
        if path.suffix.lower() in {".html", ".md", ".pdf"}:
            return "document"
    return CATEGORY_BY_SUFFIX.get(path.suffix.lower(), "other")


def collect_artifacts(root: Path) -> list[dict]:
    artifacts = []
    for directory in walk_dirs(root):
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            continue
        for child in children:
            category = classify_path(child)
            if child.is_dir():
                if category == "application":
                    artifacts.append(
                        {
                            "path": str(child.resolve()),
                            "relative_path": str(child.resolve().relative_to(root.resolve())),
                            "name": child.name,
                            "category": category,
                            "size_bytes": 0,
                        }
                    )
                continue
            if category == "other":
                continue
            try:
                size_bytes = child.stat().st_size
            except OSError:
                size_bytes = 0
            artifacts.append(
                {
                    "path": str(child.resolve()),
                    "relative_path": str(child.resolve().relative_to(root.resolve())),
                    "name": child.name,
                    "category": category,
                    "size_bytes": size_bytes,
                }
            )
    return artifacts


def extract_artifact_refs(qc_paths: list[Path]) -> list[str]:
    refs = set()
    for qc_path in qc_paths:
        if not qc_path.exists():
            continue
        text = qc_path.read_text(encoding="utf-8")
        for match in ARTIFACT_REF_RE.finditer(text):
            refs.add(match.group(1))
    return sorted(refs)


def collect_qc_referenced_artifacts(root: Path, qc_paths: list[Path]) -> list[dict]:
    artifacts = []
    seen = set()
    candidates: list[Path] = []
    for qc_path in qc_paths:
        if not qc_path.exists():
            continue
        text = qc_path.read_text(encoding="utf-8")
        include_dashboard_screenshot_set = False
        for match in ARTIFACT_REF_RE.finditer(text):
            candidate = (qc_path.parent / match.group(1)).resolve()
            candidates.append(candidate)
            if candidate.name.startswith("qc-screenshot-dashboard-"):
                include_dashboard_screenshot_set = True
        if include_dashboard_screenshot_set:
            candidates.extend(sorted(qc_path.parent.glob("qc-screenshot-dashboard-*")))
            candidates.extend(sorted(qc_path.parent.glob("qc-walkthrough-dashboard.*")))

    for candidate in unique_paths(candidates):
        if not candidate.exists() or not candidate.is_file():
            continue
        category = classify_path(candidate)
        if category == "other":
            continue
        if str(candidate) in seen:
            continue
        seen.add(str(candidate))
        try:
            size_bytes = candidate.stat().st_size
        except OSError:
            size_bytes = 0
        artifacts.append(
            {
                "path": str(candidate),
                "relative_path": display_path(candidate, root, qc_paths),
                "name": candidate.name,
                "category": category,
                "size_bytes": size_bytes,
            }
        )
    return artifacts


def find_files_by_name(root: Path, names: list[str]) -> list[Path]:
    wanted = {name.lower() for name in names}
    matches = []
    if not wanted:
        return matches
    for directory in walk_dirs(root, max_depth=6):
        try:
            children = sorted(directory.iterdir(), key=lambda child: child.name)
        except OSError:
            continue
        for child in children:
            if child.is_file() and child.name.lower() in wanted:
                matches.append(child.resolve())
    return unique_paths(matches)


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def walkthrough_selection_report(artifacts: list[dict], deliverables_root: Path | None = None) -> dict:
    walkthroughs = [
        artifact
        for artifact in artifacts
        if artifact["category"] == "media" and WALKTHROUGH_NAME_RE.search(artifact["name"])
    ]
    root = deliverables_root.resolve() if deliverables_root is not None else None
    project_scoped = [
        artifact
        for artifact in walkthroughs
        if root is not None and is_relative_to(Path(str(artifact.get("path", ""))), root)
    ]

    def sort_key(artifact: dict) -> tuple[int, str]:
        relative = str(artifact.get("relative_path", "")).lower()
        name = str(artifact.get("name", "")).lower()
        preferred = relative.startswith("review-pack/runtime/qc-walkthrough.") or name.startswith("qc-walkthrough.")
        return (0 if preferred else 1, relative or name)

    if project_scoped:
        selected = []
        for artifact in sorted(project_scoped, key=sort_key):
            item = dict(artifact)
            item["selection_scope"] = "project"
            item["selection_reason"] = "Project-scoped walkthrough under deliverables_root; preferred over foreign QC/reference media."
            selected.append(item)
        return {
            "mode": "project_scoped",
            "reason": "Selected walkthrough media inside deliverables_root.",
            "deliverables_root": str(root) if root else "",
            "candidate_count": len(walkthroughs),
            "project_scoped_count": len(project_scoped),
            "fallback_count": 0,
            "artifacts": selected,
        }

    selected = []
    for artifact in sorted(walkthroughs, key=sort_key):
        item = dict(artifact)
        item["selection_scope"] = "fallback"
        item["selection_reason"] = "Fallback only: no project-scoped walkthrough media found under deliverables_root."
        selected.append(item)
    return {
        "mode": "fallback_foreign" if selected else "none",
        "reason": "No project-scoped walkthrough media found under deliverables_root."
        if selected
        else "No walkthrough media artifacts found.",
        "deliverables_root": str(root) if root else "",
        "candidate_count": len(walkthroughs),
        "project_scoped_count": 0,
        "fallback_count": len(selected),
        "artifacts": selected,
    }


def find_walkthrough_artifacts(artifacts: list[dict], deliverables_root: Path | None = None) -> list[dict]:
    return walkthrough_selection_report(artifacts, deliverables_root).get("artifacts", [])


def infer_walkthrough_requirement(
    *,
    root: Path,
    artifacts: list[dict],
    brief_paths: list[Path],
    qc_paths: list[Path],
) -> dict:
    reasons: list[str] = []
    text = read_existing_text(brief_paths + qc_paths)
    lowered_text = text.lower()
    html_artifacts = [
        artifact
        for artifact in artifacts
        if artifact["category"] == "document" and Path(artifact["name"]).suffix.lower() in {".html", ".htm"}
    ]
    application_artifacts = [artifact for artifact in artifacts if artifact["category"] == "application"]

    if application_artifacts:
        names = ", ".join(artifact["relative_path"] for artifact in application_artifacts[:3])
        reasons.append(f"Native/packaged application artifact detected ({names}).")

    if html_artifacts and INTERACTIVE_WEB_KEYWORD_RE.search(text):
        keyword = INTERACTIVE_WEB_KEYWORD_RE.search(text).group(0)
        reasons.append(f"Brief/QC language indicates an interactive browser surface ({keyword}).")

    if html_artifacts and any(
        token in root.name.lower()
        for token in ("dashboard", "portal", "console", "app", "admin", "workspace", "game")
    ):
        reasons.append(f"Deliverables root name suggests an interactive surface ({root.name}).")

    if reasons:
        return {
            "level": "required",
            "reasons": reasons,
        }

    if html_artifacts:
        if STATIC_WEBSITE_KEYWORD_RE.search(text):
            reasons.append(
                "HTML deliverable detected, but surrounding brief/QC language reads as brochure/marketing rather than interactive product flow."
            )
        else:
            reasons.append("HTML deliverable detected. Walkthrough video is useful when motion, JS state, or flow quality matter.")
        return {
            "level": "recommended",
            "reasons": reasons,
        }

    return {
        "level": "not_needed",
        "reasons": ["No browser/native interactive artifact was detected in the review-pack inputs."],
    }


def build_spotlight(root: Path, artifacts: list[dict], qc_paths: list[Path], max_items: int) -> list[dict]:
    spotlight = []
    seen = set()

    artifact_refs = extract_artifact_refs(qc_paths)
    for path in find_files_by_name(root, artifact_refs):
        resolved = str(path)
        if resolved in seen:
            continue
        seen.add(resolved)
        spotlight.append(
            {
                "path": resolved,
                "relative_path": str(path.relative_to(root.resolve())),
                "category": classify_path(path),
                "reason": "Referenced by QC report.",
            }
        )

    for artifact in find_walkthrough_artifacts(artifacts, root):
        if len(spotlight) >= max_items:
            break
        if artifact["path"] in seen:
            continue
        seen.add(artifact["path"])
        spotlight.append(
            {
                "path": artifact["path"],
                "relative_path": artifact["relative_path"],
                "category": artifact["category"],
                "reason": "Walkthrough video artifact.",
            }
        )

    for artifact in artifacts:
        if len(spotlight) >= max_items:
            break
        if artifact["name"] not in PRIORITY_NAMES:
            continue
        if artifact["path"] in seen:
            continue
        seen.add(artifact["path"])
        spotlight.append(
            {
                "path": artifact["path"],
                "relative_path": artifact["relative_path"],
                "category": artifact["category"],
                "reason": "Priority artifact surface.",
            }
        )

    preferred_categories = ("document", "image", "media", "data", "application")
    for category in preferred_categories:
        for artifact in artifacts:
            if len(spotlight) >= max_items:
                break
            if artifact["category"] != category or artifact["path"] in seen:
                continue
            seen.add(artifact["path"])
            spotlight.append(
                {
                    "path": artifact["path"],
                    "relative_path": artifact["relative_path"],
                    "category": artifact["category"],
                    "reason": f"Representative {category} artifact.",
                }
            )
    return spotlight


def build_report(args: argparse.Namespace) -> dict:
    root = Path(args.deliverables_root).expanduser().resolve()
    brief_paths = [Path(path).expanduser().resolve() for path in args.brief]
    qc_paths = [Path(path).expanduser().resolve() for path in args.qc_report]
    artifacts = collect_artifacts(root)
    existing_paths = {artifact["path"] for artifact in artifacts}
    for artifact in collect_qc_referenced_artifacts(root, qc_paths):
        if artifact["path"] in existing_paths:
            continue
        artifacts.append(artifact)
        existing_paths.add(artifact["path"])

    counts = {}
    categorized = {}
    for category in ("document", "image", "media", "data", "application", "other"):
        category_items = [artifact for artifact in artifacts if artifact["category"] == category]
        counts[category] = len(category_items)
        categorized[category] = category_items[: args.max_files_per_category]

    spotlight = build_spotlight(root, artifacts, qc_paths, max_items=10)
    walkthrough_selection = walkthrough_selection_report(artifacts, root)
    walkthrough_artifacts = walkthrough_selection.get("artifacts", [])
    walkthrough_requirement = infer_walkthrough_requirement(
        root=root,
        artifacts=artifacts,
        brief_paths=brief_paths,
        qc_paths=qc_paths,
    )

    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "deliverables_root": str(root),
        "briefs": [str(path) for path in brief_paths],
        "qc_reports": [str(path) for path in qc_paths],
        "max_files_per_category": args.max_files_per_category,
        "artifacts_by_category_note": "Per-category listings are capped for scanability; see artifact_counts for full totals.",
        "artifact_counts": counts,
        "walkthrough_artifacts": walkthrough_artifacts,
        "walkthrough_selection": {key: value for key, value in walkthrough_selection.items() if key != "artifacts"},
        "walkthrough_requirement": walkthrough_requirement,
        "spotlight_artifacts": spotlight,
        "artifacts_by_category": categorized,
        "verdict": "PASS" if spotlight or artifacts else "FAIL",
    }


def render_markdown(report: dict) -> str:
    def escape_cell(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        "# Review Pack",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Deliverables root:** {report['deliverables_root']}",
        f"**Verdict:** {report['verdict']}",
        f"**Walkthrough videos:** {len(report.get('walkthrough_artifacts', []))}",
        f"**Walkthrough requirement:** {report.get('walkthrough_requirement', {}).get('level', 'unknown')}",
        f"**Walkthrough selection:** {report.get('walkthrough_selection', {}).get('mode', 'unknown')} — {report.get('walkthrough_selection', {}).get('reason', '')}",
        "",
        "## Artifact Counts",
        "",
        "| Category | Count |",
        "|----------|-------|",
    ]
    for category, count in report["artifact_counts"].items():
        lines.append(f"| {category} | {count} |")

    lines.extend(
        [
            "",
            f"Per-category artifact lists below show the first {report.get('max_files_per_category', 0)} file(s) in each category. Counts above are full totals.",
            "",
            "## Spotlight Artifacts",
            "",
            "| Category | Relative Path | Reason |",
            "|----------|---------------|--------|",
        ]
    )
    if report["spotlight_artifacts"]:
        for item in report["spotlight_artifacts"]:
            lines.append(
                f"| {item['category']} | {escape_cell(item['relative_path'])} | {escape_cell(item['reason'])} |"
            )
    else:
        lines.append("| — | — | No spotlight artifacts identified. |")

    lines.append("")
    lines.extend(["## Walkthrough Requirement", ""])
    requirement = report.get("walkthrough_requirement", {})
    lines.append(f"- Level: {requirement.get('level', 'unknown')}")
    for reason in requirement.get("reasons", []):
        lines.append(f"- {reason}")
    lines.append("")

    lines.extend(["## Walkthrough Videos", ""])
    walkthrough_artifacts = report.get("walkthrough_artifacts", [])
    if walkthrough_artifacts:
        for item in walkthrough_artifacts:
            lines.append(f"- {item['relative_path']}")
    else:
        lines.append("- None")
    lines.append("")

    limit = report.get("max_files_per_category", 0)
    for category, items in report["artifacts_by_category"].items():
        suffix = f" (first {limit} shown)" if limit else ""
        lines.extend([f"## {category.title()} Artifacts{suffix}", ""])
        if not items:
            lines.append("- None")
            lines.append("")
            continue
        for item in items:
            lines.append(f"- {item['relative_path']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    report = build_report(args)

    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")

    print(f"verdict={report['verdict']}")
    print(f"spotlight_count={len(report['spotlight_artifacts'])}")
    print(f"json_report={json_out}")
    print(f"markdown_report={markdown_out}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
