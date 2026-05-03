#!/usr/bin/env python3
"""
Verify that a delivery or re-delivery ticket points to a real client review surface.

This script is a delivery-specific guardrail. It answers the client's basic
question: "Where can I review this right now?" For code/mobile deliveries it
can also verify that the canonical GitHub review surface was updated after the
delivery ticket opened.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"
TICKET_TS_FMT = "%Y-%m-%dT%H:%M"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticket-path", required=True, help="Delivery or re-delivery ticket path.")
    parser.add_argument("--json-out", required=True, help="Where to write the JSON report.")
    parser.add_argument("--markdown-out", required=True, help="Where to write the markdown report.")
    return parser.parse_args()


def parse_scalar(value: str) -> object:
    text = value.strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    return text.strip("\"'")


def parse_frontmatter_map(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = {}
    for raw_line in parts[1].splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)
    return data


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True)


def check_github_repo(repo_slug: str, access_subject: str, created_at: str) -> list[dict]:
    checks: list[dict] = []

    repo_view = run_command(
        [
            "gh",
            "repo",
            "view",
            repo_slug,
            "--json",
            "name,url,visibility,defaultBranchRef",
        ]
    )
    repo_exists = repo_view.returncode == 0
    repo_info = {}
    if repo_exists:
        try:
            repo_info = json.loads(repo_view.stdout)
        except json.JSONDecodeError:
            repo_exists = False

    checks.append(
        {
            "name": "github_repo_exists",
            "ok": repo_exists,
            "details": repo_info.get("url", repo_view.stderr.strip() or f"Could not view {repo_slug}."),
        }
    )
    if not repo_exists:
        return checks

    branch = repo_info.get("defaultBranchRef", {}).get("name") or "main"
    commit_result = run_command(
        [
            "gh",
            "api",
            f"repos/{repo_slug}/commits/{branch}",
            "--jq",
            "{sha: .sha, date: .commit.committer.date, message: .commit.message}",
        ]
    )
    commit_info = {}
    latest_commit_ok = commit_result.returncode == 0
    if latest_commit_ok:
        try:
            commit_info = json.loads(commit_result.stdout)
        except json.JSONDecodeError:
            latest_commit_ok = False

    if latest_commit_ok:
        ticket_created = datetime.strptime(created_at, TICKET_TS_FMT)
        latest_commit = datetime.strptime(commit_info["date"], "%Y-%m-%dT%H:%M:%SZ")
        updated_after_ticket = latest_commit >= ticket_created
    else:
        updated_after_ticket = False

    checks.append(
        {
            "name": "github_repo_updated_after_ticket_created",
            "ok": latest_commit_ok and updated_after_ticket,
            "details": (
                f"Latest commit {commit_info['sha'][:12]} at {commit_info['date']}."
                if latest_commit_ok
                else commit_result.stderr.strip() or "Could not read latest commit."
            ),
        }
    )

    if access_subject:
        access_result = run_command(
            [
                "gh",
                "api",
                f"repos/{repo_slug}/collaborators/{access_subject}",
                "--silent",
            ]
        )
        checks.append(
            {
                "name": "github_repo_access_verified",
                "ok": access_result.returncode == 0,
                "details": (
                    f"Collaborator access active for {access_subject}."
                    if access_result.returncode == 0
                    else access_result.stderr.strip() or f"Collaborator access not verified for {access_subject}."
                ),
            }
        )

    return checks


def check_url(url: str) -> list[dict]:
    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=10) as response:
            status = response.status
        ok = 200 <= status < 400
        details = f"HEAD {status} for {url}"
    except Exception as exc:  # noqa: BLE001
        ok = False
        details = f"{url}: {exc}"

    return [
        {
            "name": "review_url_reachable",
            "ok": ok,
            "details": details,
        }
    ]


def build_report(ticket_path: Path) -> dict:
    data = parse_frontmatter_map(ticket_path)
    created_at = str(data.get("created", "")).strip()
    surface_type = str(data.get("delivery_surface_type", "")).strip()
    surface_ref = str(data.get("delivery_surface_ref", "")).strip()
    access_subject = str(data.get("delivery_surface_access_subject", "")).strip()

    checks = [
        {
            "name": "delivery_surface_type_present",
            "ok": bool(surface_type),
            "details": surface_type or "Missing `delivery_surface_type` in ticket frontmatter.",
        },
        {
            "name": "delivery_surface_ref_present",
            "ok": bool(surface_ref),
            "details": surface_ref or "Missing `delivery_surface_ref` in ticket frontmatter.",
        },
    ]

    if surface_type == "github_repo" and surface_ref and created_at:
        checks.extend(check_github_repo(surface_ref, access_subject, created_at))
    elif surface_type in {"web_url", "download_link"} and surface_ref:
        checks.extend(check_url(surface_ref))
    elif surface_type == "platform_distribution":
        checks.append(
            {
                "name": "platform_distribution_reference_present",
                "ok": bool(surface_ref),
                "details": surface_ref or "Platform distribution requires a build/channel identifier or URL.",
            }
        )
    elif surface_type == "attachment_bundle":
        checks.append(
            {
                "name": "attachment_bundle_reference_present",
                "ok": bool(surface_ref),
                "details": surface_ref or "Attachment-bundle deliveries must describe the attached bundle or zip.",
            }
        )

    verdict = "PASS" if all(check["ok"] for check in checks) else "FAIL"
    return {
        "generated_at": datetime.now().strftime(TIMESTAMP_FMT),
        "ticket_path": str(ticket_path),
        "ticket_id": data.get("id", ""),
        "ticket_title": data.get("title", ""),
        "delivery_surface_type": surface_type,
        "delivery_surface_ref": surface_ref,
        "delivery_surface_access_subject": access_subject,
        "checks": checks,
        "verdict": verdict,
    }


def render_markdown(report: dict) -> str:
    def esc(value: str) -> str:
        return value.replace("|", "\\|")

    lines = [
        "# Review Surface Check",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Ticket:** {report['ticket_id']} — {report['ticket_title']}",
        f"**Surface type:** {report['delivery_surface_type'] or '(missing)'}",
        f"**Surface ref:** {report['delivery_surface_ref'] or '(missing)'}",
        f"**Verdict:** {report['verdict']}",
        "",
        "## Checks",
        "",
        "| Check | Status | Details |",
        "|------|--------|---------|",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['name']} | {'PASS' if check['ok'] else 'FAIL'} | {esc(str(check['details']))} |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    ticket_path = Path(args.ticket_path).expanduser().resolve()
    json_out = Path(args.json_out).expanduser().resolve()
    markdown_out = Path(args.markdown_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)

    report = build_report(ticket_path)
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_out.write_text(render_markdown(report), encoding="utf-8")

    print(f"verdict={report['verdict']}")
    for check in report["checks"]:
        print(f"{check['name']}={'PASS' if check['ok'] else 'FAIL'}")
    print(f"json_report={json_out}")
    print(f"markdown_report={markdown_out}")
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
