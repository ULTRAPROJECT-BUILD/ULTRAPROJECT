#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path


def platform_dir() -> Path:
    return Path(
        os.environ.get("PLATFORM_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or Path.cwd()
    ).resolve()


def summarize_tool_call(data: dict) -> tuple[str, str, str]:
    tool = data.get("tool_name", "?")
    session = str(data.get("session_id", "?"))[:8]
    status = "FAIL" if "error" in data or data.get("tool_error") else "OK"
    tool_input = data.get("tool_input", {})

    if tool in ("Edit", "Write", "NotebookEdit"):
        detail = tool_input.get("file_path", "?")
    elif tool == "MultiEdit":
        paths = [edit.get("file_path", "?") for edit in tool_input.get("edits", [])]
        detail = ", ".join(paths[:3])
    elif tool == "Bash":
        command = tool_input.get("command", "?")
        detail = command[:100] + ("..." if len(command) > 100 else "")
    elif tool == "send_email":
        detail = "to={} subj={}".format(
            tool_input.get("to", "?"),
            str(tool_input.get("subject", "?"))[:50],
        )
    elif tool == "Read":
        detail = tool_input.get("file_path", "?")
    elif tool in ("Grep", "Glob"):
        detail = "pattern={} path={}".format(
            str(tool_input.get("pattern", "?"))[:40],
            tool_input.get("path", "."),
        )
    else:
        raw = str(tool_input)
        detail = raw[:100] + ("..." if len(raw) > 100 else "")

    return session, status, f"{tool} | {detail}"


def main() -> int:
    raw_input = sys.stdin.read()
    try:
        data = json.loads(raw_input or "{}")
    except json.JSONDecodeError:
        data = {}

    session, status, detail = summarize_tool_call(data)
    timestamp = dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    log_line = f"{timestamp} | {session} | {status} | {detail}"

    log_path = platform_dir() / "logs" / "audit.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(log_line + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
