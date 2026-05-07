#!/bin/bash
# Hook: PostToolUse + PostToolUseFailure — logs all tool calls (success and failure)
# Appends one line per tool call for debugging and compliance

INPUT=$(cat)

HOOK_INPUT="$INPUT" python3 << 'PYLOG'
import os
import sys, json, datetime
from pathlib import Path

data = json.loads(os.environ.get("HOOK_INPUT", "{}"))
tool = data.get("tool_name", "?")
session = str(data.get("session_id", "?"))[:8]

# Determine if this was a success or failure
# PostToolUseFailure includes an error field
is_failure = "error" in data or data.get("tool_error")
status = "FAIL" if is_failure else "OK"

# Extract key info based on tool type
detail = ""
ti = data.get("tool_input", {})
if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
    if tool == "MultiEdit":
        paths = [e.get("file_path", "?") for e in ti.get("edits", [])]
        detail = ", ".join(paths[:3])
    else:
        detail = ti.get("file_path", "?")
elif tool == "Bash":
    cmd = ti.get("command", "?")
    detail = cmd[:100] + ("..." if len(cmd) > 100 else "")
elif tool == "send_email":
    detail = "to={} subj={}".format(ti.get("to", "?"), ti.get("subject", "?")[:50])
elif tool == "Read":
    detail = ti.get("file_path", "?")
elif tool in ("Grep", "Glob"):
    detail = "pattern={} path={}".format(ti.get("pattern", "?")[:40], ti.get("path", "."))
else:
    raw = str(ti)
    detail = raw[:100] + ("..." if len(raw) > 100 else "")

ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
line = f"{ts} | {session} | {status} | {tool} | {detail}"

platform_dir = Path(os.environ.get("PLATFORM_DIR", Path.cwd())).resolve()
log_path = platform_dir / "logs" / "audit.log"
log_path.parent.mkdir(parents=True, exist_ok=True)

with log_path.open("a", encoding="utf-8") as f:
    f.write(line + "\n")
PYLOG

exit 0
