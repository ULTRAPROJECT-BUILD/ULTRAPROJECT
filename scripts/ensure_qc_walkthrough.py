#!/usr/bin/env python3
"""
Ensure a QC walkthrough artifact exists for interactive browser/native deliverables.

This is a best-effort helper for quality-check. It infers whether a walkthrough
video is required, recommended, or unnecessary, then tries to capture one using
the existing capture_walkthrough_video.py script.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
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
MEDIA_SUFFIXES = {".mp4", ".mov", ".webm"}
HTML_SUFFIXES = {".html", ".htm"}
APP_SUFFIXES = {".app", ".exe"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deliverables-root", required=True, help="Deliverables root directory.")
    parser.add_argument("--brief", action="append", default=[], help="Optional creative brief path(s).")
    parser.add_argument("--qc-report", action="append", default=[], help="Optional QC report path(s).")
    parser.add_argument("--url", help="Explicit URL to record for browser/web capture.")
    parser.add_argument("--launch-path", help="Explicit desktop app path to open before capture.")
    parser.add_argument("--output", help="Output video path. Defaults to {deliverables_root}/qc-walkthrough.mp4.")
    parser.add_argument("--duration", type=float, default=8.0, help="Recording duration in seconds.")
    parser.add_argument("--display-id", type=int, default=0, help="Desktop capture display ID.")
    parser.add_argument("--fps", type=int, default=12, help="Desktop capture FPS.")
    parser.add_argument("--audio-device", default="none", help="Desktop capture audio device.")
    parser.add_argument("--open-wait-seconds", type=float, default=2.0, help="Wait after opening app bundle.")
    parser.add_argument("--json-out", help="Optional JSON report path.")
    parser.add_argument("--plan-only", action="store_true", help="Infer plan only; do not record.")
    return parser.parse_args()


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def walk_files(root: Path, max_depth: int = 5) -> list[Path]:
    discovered: list[Path] = []
    stack = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda child: child.name, reverse=True)
        except OSError:
            continue
        for child in children:
            if child.is_dir():
                if child.suffix.lower() == ".app":
                    discovered.append(child.resolve())
                elif depth < max_depth and child.name not in {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}:
                    stack.append((child, depth + 1))
            else:
                discovered.append(child.resolve())
    return sorted(set(discovered), key=lambda path: str(path))


def read_existing_text(paths: list[Path]) -> str:
    parts: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "\n".join(parts)


def find_existing_walkthrough(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES and WALKTHROUGH_NAME_RE.search(path.name):
            return path
    return None


def find_html_entrypoint(paths: list[Path]) -> Path | None:
    html_files = [path for path in paths if path.is_file() and path.suffix.lower() in HTML_SUFFIXES]
    for preferred in ("index.html", "app.html"):
        for path in html_files:
            if path.name.lower() == preferred:
                return path
    return html_files[0] if html_files else None


def find_application(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.suffix.lower() in APP_SUFFIXES:
            return path
    return None


def infer_requirement(*, root: Path, paths: list[Path], brief_paths: list[Path], qc_paths: list[Path]) -> dict:
    reasons: list[str] = []
    text = read_existing_text(brief_paths + qc_paths)
    html_entry = find_html_entrypoint(paths)
    application = find_application(paths)

    if application is not None:
        reasons.append(f"Native/packaged application artifact detected ({application.name}).")
        return {"level": "required", "reasons": reasons}

    if html_entry is not None and INTERACTIVE_WEB_KEYWORD_RE.search(text):
        keyword = INTERACTIVE_WEB_KEYWORD_RE.search(text).group(0)
        reasons.append(f"Brief/QC language indicates an interactive browser surface ({keyword}).")
        return {"level": "required", "reasons": reasons}

    if html_entry is not None and any(
        token in root.name.lower() for token in ("dashboard", "portal", "console", "app", "admin", "workspace", "game")
    ):
        reasons.append(f"Deliverables root name suggests an interactive browser surface ({root.name}).")
        return {"level": "required", "reasons": reasons}

    if html_entry is not None:
        if STATIC_WEBSITE_KEYWORD_RE.search(text):
            reasons.append("HTML deliverable detected and surrounding language reads like a brochure/marketing surface.")
        else:
            reasons.append("HTML deliverable detected; walkthrough is useful when flow or motion quality matters.")
        return {"level": "recommended", "reasons": reasons}

    return {"level": "not_needed", "reasons": ["No browser/native interactive artifact detected."]}


def plan_capture(
    *,
    deliverables_root: Path,
    brief_paths: list[Path],
    qc_paths: list[Path],
    explicit_url: str | None,
    explicit_launch_path: str | None,
    output_path: Path,
) -> dict:
    paths = walk_files(deliverables_root)
    requirement = infer_requirement(root=deliverables_root, paths=paths, brief_paths=brief_paths, qc_paths=qc_paths)
    existing = find_existing_walkthrough(paths)
    if existing is not None:
        return {
            "status": "existing",
            "requirement": requirement,
            "mode": "existing",
            "output_path": str(existing),
            "reasons": [f"Existing walkthrough artifact found at {existing}."],
        }

    if requirement["level"] == "not_needed":
        return {
            "status": "skipped",
            "requirement": requirement,
            "mode": "skip",
            "output_path": str(output_path),
            "reasons": list(requirement["reasons"]),
        }

    if explicit_url:
        return {
            "status": "planned",
            "requirement": requirement,
            "mode": "web",
            "url": explicit_url,
            "output_path": str(output_path),
            "reasons": ["Using explicit QC URL for walkthrough capture."],
        }

    html_entry = find_html_entrypoint(paths)
    if html_entry is not None:
        return {
            "status": "planned",
            "requirement": requirement,
            "mode": "web",
            "url": html_entry.resolve().as_uri(),
            "output_path": str(output_path),
            "reasons": [f"Using inferred HTML entrypoint {html_entry.name}."],
        }

    launch_path = Path(explicit_launch_path).expanduser().resolve() if explicit_launch_path else find_application(paths)
    if launch_path is not None:
        return {
            "status": "planned",
            "requirement": requirement,
            "mode": "desktop",
            "launch_path": str(launch_path),
            "output_path": str(output_path),
            "reasons": [f"Using packaged application {launch_path.name} for desktop capture."],
        }

    return {
        "status": "unresolved",
        "requirement": requirement,
        "mode": "unknown",
        "output_path": str(output_path),
        "reasons": ["Could not infer a stable web URL or desktop app path for walkthrough capture."],
    }


def run_capture(plan: dict, *, duration: float, display_id: int, fps: int, audio_device: str, open_wait_seconds: float) -> dict:
    output_path = Path(plan["output_path"]).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    script_path = Path(__file__).resolve().parent / "capture_walkthrough_video.py"

    if plan["mode"] == "existing":
        return {
            "status": "existing",
            "output_path": plan["output_path"],
            "command": None,
        }

    if plan["mode"] == "skip":
        return {
            "status": "skipped",
            "output_path": plan["output_path"],
            "command": None,
        }

    if plan["mode"] == "unknown":
        return {
            "status": "unresolved",
            "output_path": plan["output_path"],
            "command": None,
        }

    if plan["mode"] == "desktop" and plan.get("launch_path"):
        subprocess.run(["open", plan["launch_path"]], check=False)
        if open_wait_seconds > 0:
            time.sleep(open_wait_seconds)

    if plan["mode"] == "web":
        command = [
            sys.executable,
            str(script_path),
            "web",
            "--url",
            str(plan["url"]),
            "--output",
            str(output_path),
            "--duration",
            str(duration),
            "--scroll",
        ]
    else:
        command = [
            sys.executable,
            str(script_path),
            "desktop",
            "--output",
            str(output_path),
            "--duration",
            str(duration),
            "--display-id",
            str(display_id),
            "--fps",
            str(fps),
            "--audio-device",
            str(audio_device),
        ]

    result = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "status": "captured" if result.returncode == 0 and output_path.exists() else "failed",
        "output_path": str(output_path),
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def write_json_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    deliverables_root = Path(args.deliverables_root).expanduser().resolve()
    brief_paths = [Path(path).expanduser().resolve() for path in args.brief]
    qc_paths = [Path(path).expanduser().resolve() for path in args.qc_report]
    output_path = Path(args.output).expanduser().resolve() if args.output else deliverables_root / "qc-walkthrough.mp4"

    plan = plan_capture(
        deliverables_root=deliverables_root,
        brief_paths=brief_paths,
        qc_paths=qc_paths,
        explicit_url=args.url,
        explicit_launch_path=args.launch_path,
        output_path=output_path,
    )

    capture = {"status": "planned-only"} if args.plan_only else run_capture(
        plan,
        duration=args.duration,
        display_id=args.display_id,
        fps=args.fps,
        audio_device=args.audio_device,
        open_wait_seconds=args.open_wait_seconds,
    )

    payload = {
        "generated_at": now(),
        "deliverables_root": str(deliverables_root),
        "requirement": plan["requirement"],
        "plan": plan,
        "capture": capture,
    }

    if args.json_out:
        write_json_report(Path(args.json_out).expanduser().resolve(), payload)

    print(f"requirement={plan['requirement']['level']}")
    print(f"mode={plan['mode']}")
    print(f"status={capture['status']}")
    print(f"output={plan['output_path']}")

    if args.plan_only:
        return 0
    if plan["requirement"]["level"] == "required" and capture["status"] not in {"captured", "existing"}:
        return 1
    if capture["status"] == "failed":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
