#!/usr/bin/env python3
"""
Reserve and audit WebSearch/WebFetch usage for the research-context skill.

The helper is intentionally file-backed and deterministic: every attempted
search/fetch must be reserved before the model performs it, and every
reservation is recorded even if the later network call fails. It is a logger,
not a gate.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_KINDS = {"WebSearch", "WebFetch"}
VALID_STATUSES = {"ok", "zero_results", "blocked", "error", "skipped"}
TIMESTAMP_FMT = "%Y-%m-%dT%H:%M:%S"


def now() -> str:
    return datetime.now().astimezone().strftime(TIMESTAMP_FMT)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create a fresh reservation ledger.")
    init.add_argument("--ledger", required=True, help="Path to the JSON ledger.")
    init.add_argument("--project", required=True, help="Project slug.")
    init.add_argument("--websearch-per-category", type=int, help="Legacy informational WebSearch annotation.")
    init.add_argument("--webfetch-per-category", type=int, help="Legacy informational WebFetch annotation.")
    init.add_argument("--categories", nargs="+", required=True, help="Fixed research categories.")

    reserve = subparsers.add_parser("reserve", help="Reserve one WebSearch or WebFetch call.")
    reserve.add_argument("--ledger", required=True, help="Path to the JSON ledger.")
    reserve.add_argument("--category", required=True, help="Research category.")
    reserve.add_argument("--kind", required=True, choices=sorted(VALID_KINDS), help="Call kind.")
    reserve.add_argument("--query", default="", help="Search query for WebSearch reservations.")
    reserve.add_argument("--url", default="", help="URL for WebFetch reservations.")

    record = subparsers.add_parser("record", help="Record the result of a reservation.")
    record.add_argument("--ledger", required=True, help="Path to the JSON ledger.")
    record.add_argument("--reservation-id", required=True, help="Reservation ID returned by reserve.")
    record.add_argument("--status", required=True, choices=sorted(VALID_STATUSES), help="Observed result status.")
    record.add_argument("--result-count", required=True, type=int, help="Observed result count.")
    record.add_argument("--url", default="", help="Observed URL or empty string.")

    summary = subparsers.add_parser("summary", help="Summarize ledger usage.")
    summary.add_argument("--ledger", required=True, help="Path to the JSON ledger.")

    return parser.parse_args()


def write_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def error_payload(reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "reason": reason}
    payload.update(extra)
    return payload


def load_ledger(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"ledger not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"ledger is not valid JSON: {exc}") from exc


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def reservations(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    items = ledger.setdefault("reservations", [])
    if not isinstance(items, list):
        raise ValueError("ledger reservations must be a list")
    return items


def used_count(ledger: dict[str, Any], kind: str, category: str | None = None) -> int:
    count = 0
    for item in reservations(ledger):
        if item.get("kind") != kind:
            continue
        if category is not None and item.get("category") != category:
            continue
        count += 1
    return count


def category_usage(ledger: dict[str, Any]) -> dict[str, dict[str, int]]:
    usage: dict[str, dict[str, int]] = {}
    for category in ledger.get("categories", []):
        usage[category] = {
            "WebSearch": used_count(ledger, "WebSearch", category),
            "WebFetch": used_count(ledger, "WebFetch", category),
        }
    return usage


def build_summary(ledger: dict[str, Any]) -> dict[str, Any]:
    categories = ledger.get("categories", [])
    usage = category_usage(ledger)
    totals = {
        "WebSearch": used_count(ledger, "WebSearch"),
        "WebFetch": used_count(ledger, "WebFetch"),
    }
    return {
        "ok": True,
        "project": ledger.get("project"),
        "ledger": ledger.get("ledger_path"),
        "categories": categories,
        "annotations": ledger.get("annotations", {}),
        "totals": totals,
        "category_usage": usage,
        "reservation_count": len(reservations(ledger)),
    }


def command_init(args: argparse.Namespace) -> int:
    if (
        args.websearch_per_category is not None
        and args.websearch_per_category < 0
    ) or (
        args.webfetch_per_category is not None
        and args.webfetch_per_category < 0
    ):
        write_json(error_payload("negative_annotations_not_allowed"))
        return 1
    categories = list(dict.fromkeys(args.categories))
    ledger_path = Path(args.ledger).expanduser().resolve()
    ledger = {
        "schema_version": 1,
        "ledger_path": str(ledger_path),
        "project": args.project,
        "created": now(),
        "updated": now(),
        "categories": categories,
        "annotations": {
            "websearch_per_category": args.websearch_per_category,
            "webfetch_per_category": args.webfetch_per_category,
        },
        "reservations": [],
    }
    save_ledger(ledger_path, ledger)
    write_json({"ok": True, "ledger": str(ledger_path), "project": args.project, "categories": categories})
    return 0


def command_reserve(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger).expanduser().resolve()
    try:
        ledger = load_ledger(ledger_path)
        categories = ledger.get("categories", [])
        if args.category not in categories:
            categories.append(args.category)
            ledger["categories"] = categories
        category_used = used_count(ledger, args.kind, args.category)
        total_used = used_count(ledger, args.kind)
        reservation_id = f"rc-{uuid.uuid4().hex[:12]}"
        item = {
            "reservation_id": reservation_id,
            "created": now(),
            "updated": now(),
            "category": args.category,
            "kind": args.kind,
            "query": args.query,
            "url": args.url,
            "status": "reserved",
            "result_count": None,
            "result_url": "",
        }
        reservations(ledger).append(item)
        ledger["updated"] = now()
        save_ledger(ledger_path, ledger)
        write_json(
            {
                "allowed": True,
                "reservation_id": reservation_id,
                "category": args.category,
                "kind": args.kind,
                "used_after": category_used + 1,
                "total_used_after": total_used + 1,
            }
        )
        return 0
    except ValueError as exc:
        write_json({"allowed": False, "reason": "ledger_error", "details": str(exc)})
        return 1


def command_record(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger).expanduser().resolve()
    try:
        ledger = load_ledger(ledger_path)
        for item in reservations(ledger):
            if item.get("reservation_id") == args.reservation_id:
                item["status"] = args.status
                item["result_count"] = args.result_count
                item["result_url"] = args.url
                item["updated"] = now()
                ledger["updated"] = now()
                save_ledger(ledger_path, ledger)
                write_json(
                    {
                        "ok": True,
                        "reservation_id": args.reservation_id,
                        "status": args.status,
                        "result_count": args.result_count,
                        "url": args.url,
                    }
                )
                return 0
        write_json(error_payload("reservation_not_found", reservation_id=args.reservation_id))
        return 1
    except ValueError as exc:
        write_json(error_payload("ledger_error", details=str(exc)))
        return 1


def command_summary(args: argparse.Namespace) -> int:
    ledger_path = Path(args.ledger).expanduser().resolve()
    try:
        write_json(build_summary(load_ledger(ledger_path)))
        return 0
    except ValueError as exc:
        write_json(error_payload("ledger_error", details=str(exc)))
        return 1


def main() -> int:
    args = parse_args()
    if args.command == "init":
        return command_init(args)
    if args.command == "reserve":
        return command_reserve(args)
    if args.command == "record":
        return command_record(args)
    if args.command == "summary":
        return command_summary(args)
    write_json(error_payload("unknown_command", command=args.command))
    return 1


if __name__ == "__main__":
    sys.exit(main())
