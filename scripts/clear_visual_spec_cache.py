#!/usr/bin/env python3
"""Clear visual-spec helper caches."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CACHE_ROOT = REPO_ROOT / "vault" / "cache" / "visual-spec"
CATEGORIES = ("phash", "clip", "render", "schema", "llm")


def utc_now() -> str:
    """Return a timezone-aware UTC ISO timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def collect_files(cache_dir: Path) -> list[Path]:
    """Return all files beneath a cache directory."""
    if not cache_dir.exists():
        return []
    return [path for path in cache_dir.rglob("*") if path.is_file()]


def remove_empty_dirs(cache_dir: Path) -> None:
    """Remove nested empty directories while preserving the category root."""
    if not cache_dir.exists():
        return
    dirs = sorted((path for path in cache_dir.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True)
    for directory in dirs:
        try:
            directory.rmdir()
        except OSError:
            pass


def clear_category(category: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Count and optionally delete files for one cache category."""
    cache_dir = CACHE_ROOT / category
    files = collect_files(cache_dir)
    total_bytes = sum(path.stat().st_size for path in files)
    if not dry_run:
        for path in files:
            path.unlink()
        remove_empty_dirs(cache_dir)
    return {"files": len(files), "bytes": total_bytes, "deleted": not dry_run}


def clear_visual_spec_cache(what: str = "all", *, dry_run: bool = False) -> dict[str, Any]:
    """Clear selected visual-spec cache categories."""
    categories = CATEGORIES if what == "all" else (what,)
    return {
        "cleared_at": utc_now(),
        "categories": {category: clear_category(category, dry_run=dry_run) for category in categories},
    }


def write_json(data: dict[str, Any], json_out: str | None = None) -> None:
    """Write JSON to stdout and, optionally, to a file."""
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    sys.stdout.write(text)
    if json_out:
        out_path = Path(json_out).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--what", choices=(*CATEGORIES, "all"), default="all", help="Cache category to clear.")
    parser.add_argument("--dry-run", action="store_true", help="Report matching files without deleting.")
    parser.add_argument("--json-out", help="Optional path to write the JSON result.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        data = clear_visual_spec_cache(args.what, dry_run=args.dry_run)
    except Exception as exc:
        data = {"cleared_at": utc_now(), "error": str(exc), "categories": {}}
        write_json(data, args.json_out)
        return 1
    write_json(data, args.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
