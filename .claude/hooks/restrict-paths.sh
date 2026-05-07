#!/bin/bash
# Hook: PreToolUse — blocks file writes outside the platform directory
# Also blocks agent writes to .mcp.json, platform skill files (skills/*.md),
# and the hook files themselves (.claude/hooks/).
# Agents should only write within the configured platform directory.
# Exit 0 = allow, Exit 2 = block

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name',''))" 2>/dev/null)

# Check file write tools — including MultiEdit
case "$TOOL_NAME" in
    Edit|Write|NotebookEdit|MultiEdit) ;;
    *) exit 0 ;;
esac

export PLATFORM_DIR="${PLATFORM_DIR:-$(pwd)}"

# Extract file paths — MultiEdit may have multiple, others have one
HOOK_INPUT="$INPUT" python3 << 'PYCHECK'
import sys, json, os

data = json.loads(os.environ.get("HOOK_INPUT", "{}"))
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})

paths = []
if tool_name == "MultiEdit":
    for edit in tool_input.get("edits", []):
        p = edit.get("file_path", "")
        if p:
            paths.append(p)
else:
    p = tool_input.get("file_path", "")
    if p:
        paths.append(p)

platform = os.environ.get("PLATFORM_DIR", os.getcwd())
platform = os.path.realpath(platform)

# Use lowercase for all comparisons (macOS has case-insensitive filesystem)
platform_lower = platform.lower()

# Restricted exact files that agents must never modify (lowercased for comparison)
restricted_files_lower = {
    os.path.join(platform_lower, ".mcp.json"),
    os.path.join(platform_lower, ".env"),
    os.path.join(platform_lower, ".financial-secrets"),
    os.path.join(platform_lower, "system.md"),
    os.path.join(platform_lower, "claude.md"),
    os.path.join(platform_lower, "overnight-review.sh"),
    os.path.join(platform_lower, "vault", "config", "platform.md"),
    os.path.join(platform_lower, "vault", "config", ".spending-integrity"),
}

# Restricted directory prefixes — agents must never write here (lowercased)
restricted_dir_prefixes_lower = [
    os.path.join(platform_lower, "skills") + "/",
    os.path.join(platform_lower, "scripts") + "/",
    os.path.join(platform_lower, ".claude", "hooks") + "/",
    os.path.join(platform_lower, ".claude", "settings.json"),
]

for path in paths:
    real = os.path.realpath(path)
    real_lower = real.lower()

    # Must start with platform dir + /  (prevents end-to-end-automation-evil trick)
    if not (real_lower == platform_lower or real_lower.startswith(platform_lower + "/")):
        print(f"BLOCKED: File writes are restricted to the platform directory. Attempted write to: {path}", file=sys.stderr)
        sys.exit(2)

    # Block restricted infrastructure files
    if real_lower in restricted_files_lower:
        basename = os.path.basename(real_lower)
        print(f"BLOCKED: '{basename}' is restricted infrastructure. Agents cannot modify it.", file=sys.stderr)
        sys.exit(2)

    # Block platform skills and hook files
    for rd in restricted_dir_prefixes_lower:
        if rd.endswith("/"):
            # Directory prefix check
            if real_lower.startswith(rd):
                print(f"BLOCKED: Writes to {rd} are admin-only. Agents cannot modify files there.", file=sys.stderr)
                sys.exit(2)
        else:
            # Exact file check
            if real_lower == rd:
                print(f"BLOCKED: {rd} is restricted infrastructure. Agents cannot modify it.", file=sys.stderr)
                sys.exit(2)

sys.exit(0)
PYCHECK
