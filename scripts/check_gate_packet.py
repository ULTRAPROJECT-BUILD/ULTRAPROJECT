#!/usr/bin/env python3
"""
Mechanically audit a phase gate packet before a hard phase gate runs.

This blocks avoidable hard-gate failures caused by:
- stale or failing readiness packs
- phantom file references in evidence docs
- missing owner-ticket coverage for exit-criterion proof
- missing or malformed walkthrough artifacts on interactive deliverables
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

from check_phase_readiness import build_report as build_phase_readiness_report

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S %Z %z"
EVIDENCE_EXTENSIONS = {".md", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov", ".webm", ".json", ".jsonl", ".yaml", ".yml", ".txt", ".pdf"}
FILE_REF_RE = re.compile(
    r"([A-Za-z0-9._/\-]+\.(?:md|png|jpg|jpeg|webp|gif|svg|mp4|mov|webm|jsonl?|yaml|yml|txt|pdf))(?:[:#]L?\d+(?:[C:-]\d+)*)?",
    re.IGNORECASE,
)
BACKTICK_RE = re.compile(r"`([^`]+)`")
WALKTHROUGH_RE = re.compile(r"(walkthrough|playthrough|screen[-_ ]?record(?:ing)?|demo)", re.IGNORECASE)
EXIT_CRITERION_FAILURE_RE = re.compile(r"Exit criterion\s+(\d+)\s+failed:", re.IGNORECASE)
EVIDENCE_CONTEXT_RE = re.compile(
    r"(path|paths|file|files|filename|location|artifact|artifacts|evidence|proof|screenshot|screenshots|walkthrough|video|media|inventory|references?)",
    re.IGNORECASE,
)
PATH_CONTEXT_RE = re.compile(r"(path|paths|file|files|filename|location|artifact|artifacts|inventory|stored|exists?)", re.IGNORECASE)
BASENAME_SEARCH_SKIP_DIRS = {
    ".cache",
    ".git",
    ".next",
    "__pycache__",
    "build",
    "DerivedData",
    "dist",
    "node_modules",
    "target",
}
_BASENAME_SEARCH_CACHE: dict[tuple[str, tuple[str, ...], int], str | None] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-packet", required=True, help="Phase gate packet YAML path.")
    parser.add_argument("--json-out", required=True, help="Where to write the JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the markdown report.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def packet_doc_paths(packet: dict[str, Any]) -> list[Path]:
    docs: list[Path] = []
    evidence_docs = packet.get("evidence_docs", {})
    for value in evidence_docs.values():
        if isinstance(value, list):
            docs.extend(Path(item).expanduser().resolve() for item in value if str(item).strip())
        elif str(value).strip():
            docs.append(Path(str(value)).expanduser().resolve())
    return [path for path in docs if path.exists()]


def clean_candidate(candidate: str) -> str:
    if "\n" in candidate or len(candidate) > 260:
        return ""
    text = candidate.strip().strip("`").strip('"').strip("'").rstrip(".,:;)]}")
    if "*" in text:
        return ""
    text = re.sub(r"#L\d+(?:C\d+)?(?:-L?\d+(?:C\d+)?)?$", "", text)
    text = re.sub(r":\d+(?:-\d+)?$", "", text)
    return text.strip()


def candidate_extension(candidate: str) -> str:
    try:
        return Path(candidate).suffix.lower()
    except Exception:
        return ""


def is_evidence_candidate(candidate: str, *, line: str, section: str) -> bool:
    cleaned = clean_candidate(candidate)
    if not cleaned:
        return False
    ext = candidate_extension(cleaned)
    if ext not in EVIDENCE_EXTENSIONS:
        return False
    if cleaned.startswith(("/", "vault/", "clients/", "deliverables/", "snapshots/")) or "/" in cleaned:
        return True
    context = f"{section}\n{line}"
    if ext in {".md", ".json", ".jsonl", ".yaml", ".yml", ".txt"} and not PATH_CONTEXT_RE.search(context):
        return False
    return bool(EVIDENCE_CONTEXT_RE.search(context))


def iter_path_candidates(text: str) -> list[str]:
    candidates: set[str] = set()
    current_section = ""
    previous_line = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            current_section = line
        context_line = line
        if line.startswith("|"):
            context_line = f"{previous_line} {line}".strip()
        for block in BACKTICK_RE.findall(raw_line):
            if "\n" in block or len(block) > 260:
                continue
            cleaned = clean_candidate(block)
            if "." in Path(cleaned).name and is_evidence_candidate(cleaned, line=context_line, section=current_section):
                candidates.add(cleaned)
        for match in FILE_REF_RE.finditer(raw_line):
            cleaned = clean_candidate(match.group(1))
            if cleaned and is_evidence_candidate(cleaned, line=context_line, section=current_section):
                candidates.add(cleaned)
        if line:
            previous_line = line
    return sorted(candidates)


def packet_lookup_roots(packet: dict[str, Any], packet_paths: dict[str, Any]) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None, *, climb: int = 0) -> None:
        if path is None:
            return
        try:
            resolved = path.expanduser().resolve()
        except OSError:
            return
        root = resolved if resolved.is_dir() else resolved.parent
        lineage = [root]
        current = root
        for _ in range(climb):
            parent = current.parent
            if parent == current:
                break
            lineage.append(parent)
            current = parent
        for item in lineage:
            key = str(item)
            if key in seen or not item.exists():
                continue
            seen.add(key)
            roots.append(item)

    for key in ("snapshots_dir", "deliverables_root", "client_root"):
        path_text = str(packet_paths.get(key, "")).strip()
        if path_text:
            add(Path(path_text))

    for item in packet.get("proof_items", []) or []:
        for value in item.get("expected_paths", []) or []:
            path_text = str(value).strip()
            if not path_text:
                continue
            add(Path(path_text))

    review_surface = packet.get("review_surface", {}) or {}
    for group_name in ("walkthrough_artifacts", "spotlight_artifacts"):
        for artifact in review_surface.get(group_name, []) or []:
            path_text = str(artifact.get("path", "")).strip()
            if not path_text:
                continue
            add(Path(path_text))

    return roots


def resolve_by_basename_search(basename: str, roots: list[Path], *, max_depth: int = 3) -> Path | None:
    resolved_roots: list[Path] = []
    for root in roots:
        try:
            resolved_root = root.expanduser().resolve()
        except OSError:
            continue
        if resolved_root.exists() and resolved_root.is_dir():
            resolved_roots.append(resolved_root)
    cache_key = (basename, tuple(str(root) for root in resolved_roots), max_depth)
    if cache_key in _BASENAME_SEARCH_CACHE:
        cached = _BASENAME_SEARCH_CACHE[cache_key]
        return Path(cached) if cached else None

    for root in resolved_roots:
        stack: list[tuple[Path, int]] = [(root, 0)]
        seen_dirs: set[str] = set()
        while stack:
            current, depth = stack.pop()
            current_key = str(current)
            if current_key in seen_dirs:
                continue
            seen_dirs.add(current_key)
            try:
                children = list(current.iterdir())
            except OSError:
                continue
            for child in children:
                if child.is_dir():
                    if depth >= max_depth or child.name in BASENAME_SEARCH_SKIP_DIRS or child.is_symlink():
                        continue
                    stack.append((child, depth + 1))
                    continue
                if child.name == basename:
                    try:
                        resolved = child.resolve()
                    except OSError:
                        continue
                    _BASENAME_SEARCH_CACHE[cache_key] = str(resolved)
                    return resolved
    _BASENAME_SEARCH_CACHE[cache_key] = None
    return None


def resolve_candidate(candidate: str, *, doc_path: Path, packet: dict[str, Any], packet_paths: dict[str, Any]) -> Path | None:
    cleaned = clean_candidate(candidate)
    if not cleaned:
        return None
    deliverables_root = Path(packet_paths.get("deliverables_root", "")).expanduser()
    client_root = Path(packet_paths.get("client_root", "")).expanduser()
    platform_root = Path(packet_paths.get("platform_root", "")).expanduser()
    snapshots_dir = Path(packet_paths.get("snapshots_dir", "")).expanduser()
    lookup_roots = packet_lookup_roots(packet, packet_paths)

    options: list[Path] = []
    raw_path = Path(cleaned)
    if raw_path.is_absolute():
        options.append(raw_path)
    else:
        options.extend(
            [
                (doc_path.parent / cleaned),
                (snapshots_dir / cleaned),
                (deliverables_root / cleaned),
                (client_root / cleaned),
            ]
        )
        if cleaned.startswith(("Desktop/", "Documents/", "Downloads/")):
            options.append(Path.home() / cleaned)
        if cleaned.startswith("vault/"):
            options.append(platform_root / cleaned)
        elif cleaned.startswith("clients/"):
            options.append((platform_root / "vault" / cleaned))
        elif cleaned.startswith("deliverables/"):
            options.append(client_root / cleaned)
        elif cleaned.startswith("snapshots/"):
            options.append(client_root / cleaned)
        for root in lookup_roots:
            options.append(root / cleaned)

    basename = raw_path.name
    if basename == cleaned and "." in basename:
        for root in [doc_path.parent, snapshots_dir, deliverables_root, *lookup_roots]:
            candidate_path = root / basename
            options.append(candidate_path)

    for option in options:
        try:
            resolved = option.expanduser().resolve()
        except OSError:
            continue
        try:
            if resolved.exists():
                return resolved
        except OSError:
            continue
    if basename == cleaned and "." in basename:
        searched = resolve_by_basename_search(
            basename,
            [doc_path.parent, snapshots_dir, deliverables_root, *lookup_roots],
            max_depth=3,
        )
        if searched is not None:
            return searched
    return None


def collect_phantom_references(packet: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    packet_paths = packet.get("paths", {})
    for doc_path in packet_doc_paths(packet):
        try:
            text = doc_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for candidate in iter_path_candidates(text):
            if resolve_candidate(candidate, doc_path=doc_path, packet=packet, packet_paths=packet_paths) is not None:
                continue
            findings.append(
                {
                    "doc": str(doc_path),
                    "reference": candidate,
                    "details": f"{doc_path.name} references `{candidate}`, but that path does not resolve on disk.",
                }
            )
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for finding in findings:
        key = (finding["doc"], finding["reference"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)
    return deduped


def existing_expected_paths(item: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for value in item.get("expected_paths", []) or []:
        path_text = str(value).strip()
        if not path_text:
            continue
        path = Path(path_text).expanduser().resolve()
        if path.exists():
            paths.append(str(path))
    return sorted(set(paths))


def split_readiness_findings(
    readiness_report: dict[str, Any], proof_items: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exit_items = {
        int(str(item.get("key", "")).rsplit("-", 1)[-1]): item
        for item in proof_items
        if item.get("kind") == "exit_criterion" and str(item.get("key", "")).startswith("exit-criterion-")
    }
    active: list[dict[str, Any]] = []
    softened: list[dict[str, Any]] = []
    for finding in readiness_report.get("findings", []):
        details = str(finding.get("details", ""))
        match = EXIT_CRITERION_FAILURE_RE.search(details)
        if match:
            item = exit_items.get(int(match.group(1)))
            if item and item.get("owner_tickets") and existing_expected_paths(item):
                softened.append(finding)
                continue
        active.append(finding)
    return active, softened


def probe_video_contract(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name:format=format_name,duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=True, timeout=15)
        payload = json.loads(proc.stdout or "{}")
    except Exception:
        payload = {}
    stream = (payload.get("streams") or [{}])[0]
    fmt = payload.get("format") or {}
    try:
        duration = float(fmt.get("duration"))
    except (TypeError, ValueError):
        duration = None
    return {
        "codec": str(stream.get("codec_name") or "").strip().lower(),
        "format_name": str(fmt.get("format_name") or "").strip().lower(),
        "duration_seconds": duration,
    }


def evaluate_walkthrough_contract(packet: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    review_surface = packet.get("review_surface", {})
    requirement = review_surface.get("walkthrough_requirement", {}) or {}
    walkthroughs = review_surface.get("walkthrough_artifacts", []) or []
    required = str(requirement.get("level", "")).strip().lower() == "required"

    checks.append(
        {
            "name": "walkthrough_present_when_required",
            "ok": (not required) or bool(walkthroughs),
            "details": "Required walkthrough artifact is present."
            if ((not required) or walkthroughs)
            else "Interactive deliverable requires a walkthrough artifact, but none is present in the packet.",
        }
    )

    contract_ok = True
    contract_details: list[str] = []
    short_duration_findings: list[dict[str, str]] = []
    meaningful_walkthroughs: list[Path] = []
    for artifact in walkthroughs:
        path = Path(str(artifact.get("path", ""))).expanduser().resolve()
        if not path.exists():
            contract_ok = False
            contract_details.append(f"{path.name or path} is missing on disk.")
            findings.append(
                {
                    "severity": "HIGH",
                    "category": "media-contract",
                    "details": f"Walkthrough artifact is listed in the packet but missing on disk: {path}.",
                }
            )
            continue
        meta = probe_video_contract(path)
        suffix = path.suffix.lower()
        if suffix == ".mp4":
            if "mp4" not in meta["format_name"]:
                contract_ok = False
                contract_details.append(f"{path.name} uses `{meta['format_name'] or 'unknown'}` container under .mp4.")
                findings.append(
                    {
                        "severity": "HIGH",
                        "category": "media-contract",
                        "details": f"{path.name} is labeled `.mp4` but ffprobe reports `{meta['format_name'] or 'unknown'}` container.",
                    }
                )
            if meta["codec"] and meta["codec"] != "h264":
                contract_ok = False
                contract_details.append(f"{path.name} uses `{meta['codec']}` instead of H.264.")
                findings.append(
                    {
                        "severity": "HIGH",
                        "category": "media-contract",
                        "details": f"{path.name} uses `{meta['codec']}` instead of H.264, which violates the MP4 media contract.",
                    }
                )
        duration = meta["duration_seconds"]
        if required and duration is not None and duration < 8.0:
            contract_details.append(f"{path.name} is only {meta['duration_seconds']:.2f}s long.")
            short_duration_findings.append(
                {
                    "severity": "MEDIUM",
                    "category": "media-contract",
                    "details": f"{path.name} is too short to serve as a meaningful walkthrough ({meta['duration_seconds']:.2f}s).",
                }
            )
        elif required and duration is not None and duration >= 8.0:
            meaningful_walkthroughs.append(path)

    if required and short_duration_findings and not meaningful_walkthroughs:
        contract_ok = False
        findings.extend(short_duration_findings)
    elif required and short_duration_findings and meaningful_walkthroughs:
        contract_details.append(
            f"{len(short_duration_findings)} short supplemental clip(s) ignored because "
            f"{len(meaningful_walkthroughs)} meaningful walkthrough video(s) meet the duration contract."
        )

    checks.append(
        {
            "name": "walkthrough_media_contract",
            "ok": contract_ok,
            "details": "Walkthrough media contract checks passed."
            if contract_ok
            else "; ".join(contract_details) or "Walkthrough media contract failed.",
        }
    )
    return checks, findings


def build_report(packet_path: Path) -> dict[str, Any]:
    packet = load_yaml(packet_path)
    readiness_inputs = packet.get("readiness_inputs", {})
    readiness_report = build_phase_readiness_report(
        argparse.Namespace(
            project_file=readiness_inputs.get("project_file"),
            project_plan=readiness_inputs.get("project_plan"),
            phase=int(readiness_inputs.get("phase")),
            tickets_dir=readiness_inputs.get("tickets_dir"),
            artifacts_root=readiness_inputs.get("artifacts_root"),
            deliverables_root=readiness_inputs.get("deliverables_root"),
            search_root=readiness_inputs.get("search_root", []),
            brief=readiness_inputs.get("brief", []),
            evidence_doc=readiness_inputs.get("evidence_doc", []),
            json_out=str(packet_path.parent / "_unused-readiness.json"),
            markdown_out=str(packet_path.parent / "_unused-readiness.md"),
        )
    )

    packet_paths = packet.get("paths", {})
    required_path_checks: list[tuple[str, str]] = [
        ("project_file", str(packet_paths.get("project_file", ""))),
        ("project_plan", str(packet_paths.get("project_plan", ""))),
        ("tickets_dir", str(packet_paths.get("tickets_dir", ""))),
        ("snapshots_dir", str(packet_paths.get("snapshots_dir", ""))),
        ("deliverables_root", str(packet_paths.get("deliverables_root", ""))),
    ]
    packet_paths_ok = all(Path(path).expanduser().exists() for _, path in required_path_checks if path)
    packet_path_details = [
        f"{name}: {'ok' if Path(path).expanduser().exists() else 'missing'}"
        for name, path in required_path_checks
        if path
    ]

    proof_items = packet.get("proof_items", []) or []
    active_readiness_findings, softened_readiness_findings = split_readiness_findings(readiness_report, proof_items)
    ownerless_exit_items = [
        item for item in proof_items if item.get("kind") == "exit_criterion" and not item.get("owner_tickets")
    ]
    missing_expected_paths: list[dict[str, str]] = []
    for item in proof_items:
        for path_text in item.get("expected_paths", []) or []:
            resolved = Path(str(path_text)).expanduser().resolve()
            if not resolved.exists():
                missing_expected_paths.append(
                    {
                        "key": str(item.get("key", "")),
                        "path": str(resolved),
                        "details": f"{item.get('key', 'proof item')} expects `{resolved}`, but that path is missing on disk.",
                    }
                )
    phantom_refs = collect_phantom_references(packet)
    walkthrough_checks, walkthrough_findings = evaluate_walkthrough_contract(packet)
    readiness_ok = readiness_report.get("verdict") == "PASS" or not active_readiness_findings

    checks: list[dict[str, Any]] = [
        {
            "name": "gate_packet_paths_exist",
            "ok": packet_paths_ok,
            "details": "All required packet paths exist."
            if packet_paths_ok
            else "; ".join(packet_path_details),
        },
        {
            "name": "phase_readiness_passes",
            "ok": readiness_ok,
            "details": "Phase readiness passed."
            if readiness_report.get("verdict") == "PASS"
            else (
                f"Phase readiness blockers remain ({len(active_readiness_findings)} finding(s))."
                if active_readiness_findings
                else f"Phase readiness is backstopped by gate-packet proof ownership ({len(softened_readiness_findings)} exit criterion finding(s) softened)."
            ),
        },
        {
            "name": "exit_criteria_have_owner_tickets",
            "ok": not ownerless_exit_items,
            "details": "Every exit criterion has an owner ticket."
            if not ownerless_exit_items
            else f"{len(ownerless_exit_items)} exit criterion proof item(s) have no owner ticket.",
        },
        {
            "name": "proof_item_expected_paths_exist",
            "ok": not missing_expected_paths,
            "details": "All declared proof-item paths exist on disk."
            if not missing_expected_paths
            else f"{len(missing_expected_paths)} declared proof-item path(s) are missing on disk.",
        },
        {
            "name": "evidence_docs_have_no_phantom_refs",
            "ok": not phantom_refs,
            "details": "No phantom file references found in gate packet evidence docs."
            if not phantom_refs
            else f"{len(phantom_refs)} phantom file reference(s) found in gate packet evidence docs.",
        },
    ]
    checks.extend(walkthrough_checks)

    findings: list[dict[str, str]] = []
    for finding in active_readiness_findings:
        findings.append(
            {
                "severity": str(finding.get("severity", "HIGH")),
                "category": str(finding.get("category", "phase-readiness")),
                "details": str(finding.get("details", "")),
            }
        )
    for item in ownerless_exit_items:
        findings.append(
            {
                "severity": "HIGH",
                "category": "proof-ownership",
                "details": f"{item.get('key', 'exit criterion')} has no owner ticket in the gate packet.",
            }
        )
    for finding in missing_expected_paths:
        findings.append(
            {
                "severity": "HIGH",
                "category": "proof-ownership",
                "details": finding["details"],
            }
        )
    for finding in phantom_refs:
        findings.append(
            {
                "severity": "HIGH",
                "category": "verification-evidence",
                "details": finding["details"],
            }
        )
    findings.extend(walkthrough_findings)

    verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"
    return {
        "generated_at": now(),
        "gate_packet": str(packet_path),
        "project": packet.get("project", ""),
        "client": packet.get("client", ""),
        "phase": packet.get("phase"),
        "phase_title": packet.get("phase_title", ""),
        "checks": checks,
        "findings": findings,
        "verdict": verdict,
        "readiness_verdict": readiness_report.get("verdict", ""),
        "readiness_report": readiness_report,
        "softened_readiness_findings": softened_readiness_findings,
        "phantom_references": phantom_refs,
        "missing_expected_paths": missing_expected_paths,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Gate Packet Audit",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Gate packet:** `{report['gate_packet']}`",
        f"**Phase:** {report.get('phase')} — {report.get('phase_title', '')}",
        f"**Verdict:** {report['verdict']}",
        f"**Readiness verdict:** {report.get('readiness_verdict', 'unknown')}",
        "",
        "## Checks",
        "",
    ]
    for check in report.get("checks", []):
        lines.append(f"- **{check['name']}**: {'PASS' if check['ok'] else 'FAIL'} — {check['details']}")
    lines.extend(["", "## Findings", ""])
    if report.get("findings"):
        for finding in report["findings"]:
            lines.append(f"- **[{finding['severity']}] [{finding['category']}]** {finding['details']}")
    else:
        lines.append("- None.")
    if report.get("phantom_references"):
        lines.extend(["", "## Phantom References", ""])
        for finding in report["phantom_references"]:
            lines.append(f"- `{finding['doc']}` -> `{finding['reference']}`")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    packet_path = Path(args.gate_packet).expanduser().resolve()
    report = build_report(packet_path)
    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
