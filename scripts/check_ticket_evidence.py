#!/usr/bin/env python3
"""
Check ticket-specific evidence artifacts for closeout truthfulness.

This script stays intentionally lean: it is not a full gate review. It answers
two narrow but high-value questions early, at ticket closeout time:

1. Do the ticket's own handoff/closeout artifacts contradict the ticket's
   current status?
2. If the ticket claims proof/evidence artifacts, do those cited proof
   references actually resolve on disk?

Typical failures it catches:
- ticket frontmatter says `closed`, but a handoff artifact says keep it
  `in-progress`
- ticket frontmatter says `closed`, but a closeout proposal says `blocked`
- ticket work log says screenshots/walkthrough/results were captured, but the
  cited file or directory is missing
- ticket points to an evidence directory that exists but is empty
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
VALID_STATUSES = {"open", "in-progress", "blocked", "waiting", "closed", "complete"}
FENCE_RE = re.compile(r"```(?:yaml|yml|md|markdown)?\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)
STATUS_LINE_RE = re.compile(r"^\s*status:\s*([A-Za-z-]+)\s*$", re.MULTILINE)
DIRECT_STATUS_PATTERNS = [
    re.compile(r"keep\s+`?status:\s*([A-Za-z-]+)`?", re.IGNORECASE),
    re.compile(r"ticket\s+should\s+stay\s+([A-Za-z-]+)", re.IGNORECASE),
    re.compile(r"proposes?\s+`?status:\s*([A-Za-z-]+)`?", re.IGNORECASE),
]
STATUS_CONTEXT_TOKENS = ("frontmatter", "ticket", "proposal", "proposed", "intended", "updates", "handoff", "closeout")
PROOF_FILE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".mp4",
    ".mov",
    ".webm",
    ".mp3",
    ".wav",
    ".m4a",
    ".md",
    ".markdown",
    ".json",
    ".yaml",
    ".yml",
    ".pdf",
    ".html",
    ".htm",
    ".csv",
    ".tsv",
    ".txt",
}
PROOF_MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a"}
PROOF_PATH_KEYWORDS = (
    "artifact",
    "benchmark",
    "evidence",
    "proof",
    "qc-",
    "review-pack",
    "screenshot",
    "snapshot",
    "stitch",
    "verification",
    "walkthrough",
)
PROOF_PATH_PREFIXES = (
    "/" + "Users/",
    "~/",
    "Desktop/",
    "vault/",
    "clients/",
    "snapshots/",
    "artifacts/",
    "proof-packs/",
    "deliverables/",
    ".stitch/",
)
PROOF_FILENAME_RE = re.compile(
    r"(?<![A-Za-z0-9./])([A-Za-z0-9._/\-]+\.(?:png|jpg|jpeg|webp|gif|svg|mp4|mov|webm|mp3|wav|m4a|md|markdown|json|yaml|yml|pdf|html|htm|csv|tsv|txt))\b",
    re.IGNORECASE,
)
PROOF_CLAIM_RE = re.compile(
    r"\b("
    r"captur(?:e|ed|ing)|saved?|save\s+to|saved\s+as|written?\s+to|wrote|"
    r"record(?:ed|ing)|generated|exported|consolidated|proof\s+pack|review\s+pack|"
    r"results?\s+written|evidence\s+files?|screenshots?|walkthrough|video|"
    r"verification\s+(?:results?|proof)"
    r")\b",
    re.IGNORECASE,
)
SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "shards",
    "store",
    "workspaces",
    "repos",
    ".refactor-platform",
}
MAX_ARTIFACT_SCAN_DEPTH = 2
MAX_BASENAME_SEARCH_DEPTH = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-path", required=True, help="Ticket markdown path.")
    parser.add_argument("--artifacts-root", required=True, help="Artifacts directory to scan for ticket-specific evidence.")
    parser.add_argument("--json-out", required=True, help="Where to write the JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the markdown report.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def parse_scalar(value: str) -> object:
    text = value.strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    return text.strip("\"'")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1].strip("\n"), parts[2]


def parse_frontmatter_map(path: Path) -> dict:
    frontmatter, _ = split_frontmatter(path.read_text(encoding="utf-8"))
    data: dict[str, object] = {}
    current_list_key: str | None = None
    for raw_line in frontmatter.splitlines():
        if raw_line.startswith("  - ") and current_list_key:
            data.setdefault(current_list_key, [])
            cast_list = data[current_list_key]
            if isinstance(cast_list, list):
                cast_list.append(parse_scalar(raw_line[4:]))
            continue
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            current_list_key = None
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            data[key] = []
            current_list_key = key
            continue
        data[key] = parse_scalar(value)
        current_list_key = None
    return data


def normalize_status(value: object) -> str:
    text = str(value or "").strip().lower()
    if text == "complete":
        return "closed"
    return text


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def find_client_root(ticket_path: Path) -> Path:
    for parent in ticket_path.parents:
        if parent.name in {"tickets", "snapshots"}:
            return parent.parent
    return ticket_path.parent


def deliverables_root_from_artifacts_root(artifacts_root: Path) -> Path:
    return artifacts_root.parent if artifacts_root.name == "artifacts" else artifacts_root


def find_ticket_artifacts(artifacts_root: Path, ticket_id: str) -> list[Path]:
    canonical = ticket_id.strip().upper()
    compact = canonical.replace("-", "")
    patterns = [
        re.compile(rf"(?<![A-Za-z0-9]){re.escape(canonical.lower())}(?![A-Za-z0-9])"),
        re.compile(rf"(?<![A-Za-z0-9]){re.escape(compact.lower())}(?![A-Za-z0-9])"),
    ]
    matches: list[Path] = []
    if not artifacts_root.exists():
        return matches
    stack: list[tuple[Path, int]] = [(artifacts_root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for path in children:
            if path.is_dir():
                if path.name in SKIP_DIR_NAMES or depth >= MAX_ARTIFACT_SCAN_DEPTH:
                    continue
                stack.append((path, depth + 1))
                continue
            name = path.name.lower()
            rel = path.relative_to(artifacts_root).as_posix().lower()
            if any(pattern.search(name) or pattern.search(rel) for pattern in patterns):
                matches.append(path.resolve())
    return sorted(matches)


def normalize_candidate(candidate: str) -> str:
    cleaned = candidate.strip().strip("`").strip().strip("\"'")
    cleaned = cleaned.rstrip(".,:;)]}")
    return cleaned.strip()


def candidate_looks_like_proof_reference(candidate: str, *, line_text: str = "", source: str = "") -> bool:
    cleaned = normalize_candidate(candidate)
    if not cleaned or "\n" in cleaned or len(cleaned) > 260:
        return False
    if "*" in cleaned or "?" in cleaned:
        return False
    lowered = cleaned.lower()
    suffix = Path(cleaned.rstrip("/")).suffix.lower()
    line_lower = line_text.lower()
    if suffix in PROOF_MEDIA_SUFFIXES:
        return True
    if suffix in PROOF_FILE_SUFFIXES:
        if source != "bare_filename":
            return True
        basename = Path(cleaned).name.lower()
        doc_keywords = ("benchmark", "evidence", "proof", "qc", "result", "review", "snapshot", "verification", "walkthrough")
        return any(keyword in basename for keyword in doc_keywords) or any(keyword in line_lower for keyword in doc_keywords)
    if any(lowered.startswith(prefix.lower()) for prefix in PROOF_PATH_PREFIXES):
        return True
    if any(keyword in lowered for keyword in PROOF_PATH_KEYWORDS):
        return True
    if "/" in cleaned and any(part for part in cleaned.split("/") if part):
        return any(keyword in lowered for keyword in ("qc", "proof", "snapshot", "review", "benchmark"))
    return False


def find_proof_claim_lines(text: str) -> list[dict]:
    findings: list[dict] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("title:", "tags:", "#")):
            continue
        if PROOF_CLAIM_RE.search(line):
            findings.append({"line_number": line_number, "line": line[:240]})
    return findings


def classify_proof_path(path: Path) -> str:
    if path.is_dir():
        return "directory"
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return "image"
    if suffix in {".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a"}:
        return "media"
    if suffix in {".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".pdf", ".html", ".htm"}:
        return "document"
    if suffix in {".csv", ".tsv"}:
        return "data"
    return "other"


def iter_files(root: Path, *, max_depth: int) -> list[Path]:
    files: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.name in SKIP_DIR_NAMES or depth >= max_depth:
                    continue
                stack.append((child, depth + 1))
                continue
            files.append(child)
    return files


def resolve_candidate_direct(candidate: str, *, ticket_path: Path, artifacts_root: Path) -> Path | None:
    cleaned = normalize_candidate(candidate)
    if not cleaned:
        return None
    if cleaned.startswith("~"):
        resolved = Path(cleaned).expanduser().resolve()
        return resolved if resolved.exists() else None
    if cleaned.startswith("/"):
        resolved = Path(cleaned).expanduser().resolve()
        return resolved if resolved.exists() else None

    client_root = find_client_root(ticket_path)
    deliverables_root = deliverables_root_from_artifacts_root(artifacts_root)
    ticket_dir = ticket_path.parent
    repo = repo_root()
    home = Path.home()

    candidate_roots: list[Path] = []
    lowered = cleaned.lower()
    if lowered.startswith("vault/"):
        candidate_roots = [repo]
    elif lowered.startswith("clients/"):
        candidate_roots = [repo / "vault"]
    elif lowered.startswith("snapshots/"):
        candidate_roots = [client_root, deliverables_root]
    elif lowered.startswith("artifacts/"):
        candidate_roots = [deliverables_root, artifacts_root, client_root]
    elif lowered.startswith("proof-packs/"):
        candidate_roots = [deliverables_root, client_root]
    elif lowered.startswith("deliverables/"):
        candidate_roots = [client_root, deliverables_root.parent, deliverables_root]
    elif lowered.startswith("desktop/"):
        candidate_roots = [home]
    else:
        candidate_roots = [ticket_dir, deliverables_root, artifacts_root, client_root, repo, home]

    for root in candidate_roots:
        resolved = (root / cleaned).expanduser().resolve()
        if resolved.exists():
            return resolved
    return None


def candidate_allows_basename_search(candidate: str) -> bool:
    cleaned = normalize_candidate(candidate)
    basename = Path(cleaned).name.lower()
    suffix = Path(basename).suffix.lower()
    if suffix in PROOF_MEDIA_SUFFIXES:
        return True
    return any(keyword in basename for keyword in PROOF_PATH_KEYWORDS)


def resolve_candidate_by_basename(candidate: str, *, ticket_path: Path, artifacts_root: Path) -> list[Path]:
    cleaned = normalize_candidate(candidate)
    basename = Path(cleaned).name
    if not basename or "/" in basename or not candidate_allows_basename_search(cleaned):
        return []
    client_root = find_client_root(ticket_path)
    deliverables_root = deliverables_root_from_artifacts_root(artifacts_root)
    search_roots = [
        deliverables_root,
        artifacts_root,
        deliverables_root / ".stitch",
        deliverables_root / "snapshots",
        client_root / "snapshots",
    ]
    matches: list[Path] = []
    seen: set[Path] = set()
    for root in search_roots:
        if not root.exists():
            continue
        for path in iter_files(root, max_depth=MAX_BASENAME_SEARCH_DEPTH):
            if path.name != basename:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            matches.append(resolved)
    return sorted(matches)


def directory_has_proof_files(path: Path) -> bool:
    for child in iter_files(path, max_depth=2):
        if child.suffix.lower() in PROOF_FILE_SUFFIXES:
            return True
    return False


def collect_referenced_proof_paths(ticket_path: Path, artifacts_root: Path) -> list[dict]:
    text = ticket_path.read_text(encoding="utf-8")
    refs: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        candidates: list[tuple[str, str]] = []
        for block in re.findall(r"`([^`]+)`", raw_line):
            candidates.append((block, "backtick"))
        for prefix in PROOF_PATH_PREFIXES:
            pattern = re.compile(rf"({re.escape(prefix)}[^\s`\"'<>]+)")
            for match in pattern.finditer(raw_line):
                candidates.append((match.group(1), "path_prefix"))
        for match in PROOF_FILENAME_RE.finditer(raw_line):
            candidates.append((match.group(1), "bare_filename"))

        for candidate, source in candidates:
            cleaned = normalize_candidate(candidate)
            if not candidate_looks_like_proof_reference(cleaned, line_text=raw_line, source=source):
                continue
            dedupe_key = (line_number, cleaned)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            resolved = resolve_candidate_direct(cleaned, ticket_path=ticket_path, artifacts_root=artifacts_root)
            matches = [resolved] if resolved is not None else resolve_candidate_by_basename(
                cleaned, ticket_path=ticket_path, artifacts_root=artifacts_root
            )
            refs.append(
                {
                    "candidate": cleaned,
                    "line_number": line_number,
                    "line": raw_line.strip()[:240],
                    "source": source,
                    "matches": [str(path) for path in matches],
                    "resolved": bool(matches),
                    "category": classify_proof_path(matches[0]) if matches else "missing",
                }
            )
    return refs


def extract_implied_statuses(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        return []
    findings: list[dict] = []

    for pattern in DIRECT_STATUS_PATTERNS:
        for match in pattern.finditer(text):
            status = normalize_status(match.group(1))
            if status not in VALID_STATUSES:
                continue
            snippet = match.group(0).strip().replace("\n", " ")
            findings.append(
                {
                    "path": str(path),
                    "status": status,
                    "source": "direct_phrase",
                    "snippet": snippet[:200],
                }
            )

    for match in FENCE_RE.finditer(text):
        block = match.group(1)
        prelude = text[max(0, match.start() - 220) : match.start()].lower()
        if not any(token in prelude for token in STATUS_CONTEXT_TOKENS):
            continue
        for status_match in STATUS_LINE_RE.finditer(block):
            status = normalize_status(status_match.group(1))
            if status not in VALID_STATUSES:
                continue
            snippet = status_match.group(0).strip()
            findings.append(
                {
                    "path": str(path),
                    "status": status,
                    "source": "contextual_code_block",
                    "snippet": snippet[:200],
                }
            )

    deduped: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for finding in findings:
        key = (finding["path"], finding["status"], finding["snippet"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def build_report(ticket_path: Path, artifacts_root: Path) -> dict:
    ticket_text = ticket_path.read_text(encoding="utf-8")
    ticket_data = parse_frontmatter_map(ticket_path)
    ticket_id = str(ticket_data.get("id", ticket_path.stem)).strip() or ticket_path.stem
    ticket_title = str(ticket_data.get("title", ticket_path.stem)).strip()
    ticket_status = normalize_status(ticket_data.get("status", ""))
    artifacts = find_ticket_artifacts(artifacts_root, ticket_id)
    proof_claim_lines = find_proof_claim_lines(ticket_text)
    proof_references = collect_referenced_proof_paths(ticket_path, artifacts_root)

    implied_statuses: list[dict] = []
    for artifact in artifacts:
        implied_statuses.extend(extract_implied_statuses(artifact))

    contradictions: list[dict] = []
    if ticket_status:
        for finding in implied_statuses:
            if finding["status"] != ticket_status:
                contradictions.append(
                    {
                        "ticket_status": ticket_status,
                        "artifact_status": finding["status"],
                        "path": finding["path"],
                        "source": finding["source"],
                        "snippet": finding["snippet"],
                    }
                )

    missing_proof_references = [reference for reference in proof_references if not reference["resolved"]]
    empty_proof_directories: list[dict] = []
    resolved_proof_paths: list[dict] = []
    for reference in proof_references:
        if not reference["resolved"]:
            continue
        for match in reference["matches"]:
            path = Path(match)
            resolved_proof_paths.append(
                {
                    "candidate": reference["candidate"],
                    "path": match,
                    "category": classify_proof_path(path),
                }
            )
            if path.is_dir() and not directory_has_proof_files(path):
                empty_proof_directories.append(
                    {
                        "candidate": reference["candidate"],
                        "path": match,
                        "line_number": reference["line_number"],
                    }
                )

    enforce_proof_checks = ticket_status == "closed"
    proof_claims_need_artifacts = enforce_proof_checks and bool(proof_claim_lines)
    grounded_proof_claims = not proof_claims_need_artifacts or bool(proof_references)

    checks = [
        {
            "name": "ticket_status_present",
            "ok": bool(ticket_status),
            "details": ticket_status or "Ticket frontmatter missing status.",
        },
        {
            "name": "artifacts_scanned",
            "ok": True,
            "details": f"{len(artifacts)} matching artifact file(s) under {artifacts_root}.",
        },
        {
            "name": "proof_claims_grounded",
            "ok": grounded_proof_claims,
            "details": "Ticket is not closed yet; proof-grounding check skipped."
            if not enforce_proof_checks
            else (
                "Closed ticket includes concrete proof references for its evidence claims."
                if grounded_proof_claims
                else f"Found {len(proof_claim_lines)} proof/evidence claim line(s) but no concrete proof paths were cited."
            ),
        },
        {
            "name": "referenced_proof_paths_resolve",
            "ok": True if not enforce_proof_checks else not missing_proof_references,
            "details": "Ticket is not closed yet; proof-path resolution check skipped."
            if not enforce_proof_checks
            else (
                "All cited proof paths resolved on disk."
                if not missing_proof_references
                else f"{len(missing_proof_references)} cited proof path(s) did not resolve."
            ),
        },
        {
            "name": "referenced_proof_directories_populated",
            "ok": True if not enforce_proof_checks else not empty_proof_directories,
            "details": "Ticket is not closed yet; proof-directory population check skipped."
            if not enforce_proof_checks
            else (
                "All cited proof directories contain proof files."
                if not empty_proof_directories
                else f"{len(empty_proof_directories)} cited proof director(ies) exist but are empty."
            ),
        },
        {
            "name": "status_contradictions",
            "ok": not contradictions,
            "details": "No contradictory ticket artifact status proposals found."
            if not contradictions
            else f"{len(contradictions)} contradictory status proposal(s) found.",
        },
    ]

    verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"
    return {
        "generated_at": now(),
        "ticket_path": str(ticket_path.resolve()),
        "ticket_id": ticket_id,
        "ticket_title": ticket_title,
        "ticket_status": ticket_status,
        "artifacts_root": str(artifacts_root.resolve()),
        "artifacts": [str(path) for path in artifacts],
        "implied_statuses": implied_statuses,
        "contradictions": contradictions,
        "proof_claim_lines": proof_claim_lines,
        "proof_references": proof_references,
        "resolved_proof_paths": resolved_proof_paths,
        "missing_proof_references": missing_proof_references,
        "empty_proof_directories": empty_proof_directories,
        "checks": checks,
        "verdict": verdict,
    }


def render_markdown(report: dict) -> str:
    lines = [
        "# Ticket Evidence Check",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Ticket:** {report['ticket_id']} — {report['ticket_title']}",
        f"**Current ticket status:** {report['ticket_status'] or '(missing)'}",
        f"**Artifacts root:** {report['artifacts_root']}",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        icon = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- **{check['name']}**: {icon} — {check['details']}")

    lines.extend(
        [
            "",
            "## Matching Artifacts",
            "",
        ]
    )
    if report["artifacts"]:
        for path in report["artifacts"]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- No ticket-specific artifacts found.")

    lines.extend(
        [
            "",
            "## Proof Claim Lines",
            "",
        ]
    )
    if report["proof_claim_lines"]:
        for finding in report["proof_claim_lines"]:
            lines.append(f"- L{finding['line_number']}: `{finding['line']}`")
    else:
        lines.append("- None detected.")

    lines.extend(
        [
            "",
            "## Referenced Proof Paths",
            "",
        ]
    )
    if report["proof_references"]:
        for reference in report["proof_references"]:
            if reference["resolved"]:
                joined = ", ".join(f"`{path}`" for path in reference["matches"])
                lines.append(
                    f"- L{reference['line_number']} `{reference['candidate']}` → {joined} ({reference['category']})"
                )
            else:
                lines.append(f"- L{reference['line_number']} `{reference['candidate']}` → MISSING")
    else:
        lines.append("- None detected.")

    lines.extend(
        [
            "",
            "## Contradictions",
            "",
        ]
    )
    if report["contradictions"]:
        for finding in report["contradictions"]:
            lines.extend(
                [
                    f"- `{finding['path']}`",
                    f"  - ticket status: `{finding['ticket_status']}`",
                    f"  - artifact status: `{finding['artifact_status']}`",
                    f"  - source: `{finding['source']}`",
                    f"  - snippet: `{finding['snippet']}`",
                ]
            )
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "## Empty Proof Directories",
            "",
        ]
    )
    if report["empty_proof_directories"]:
        for finding in report["empty_proof_directories"]:
            lines.append(f"- L{finding['line_number']}: `{finding['path']}`")
    else:
        lines.append("- None.")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    ticket_path = Path(args.ticket_path).expanduser().resolve()
    artifacts_root = Path(args.artifacts_root).expanduser().resolve()
    report = build_report(ticket_path, artifacts_root)

    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
