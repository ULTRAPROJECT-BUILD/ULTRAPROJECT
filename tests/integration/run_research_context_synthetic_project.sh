#!/usr/bin/env bash
# Test type: live integration shell harness for research-context.
# Expects live WebSearch/WebFetch availability through the hosting agent.
set -u

CODEX_PROCESS_ISSUE_NESTED_SANDBOX=73
PROJECT="research-context-synthetic-current-ai-video"
DATE_STAMP="$(date +%Y-%m-%d)"
PROJECT_FILE="vault/clients/_platform/projects/${PROJECT}.md"
SNAPSHOTS_DIR="vault/clients/_platform/snapshots/${PROJECT}"
OUT="${SNAPSHOTS_DIR}/${DATE_STAMP}-research-context-${PROJECT}.md"
CODEX_LAST_MESSAGE="${SNAPSHOTS_DIR}/${DATE_STAMP}-research-context-live-harness-last-message.md"

skip_nested() {
  echo "CODEX_PROCESS_ISSUE_NESTED_SANDBOX: $1" >&2
  exit "$CODEX_PROCESS_ISSUE_NESTED_SANDBOX"
}

if [ -n "${CODEX_NESTED:-}" ] || [ -n "${CODEX_RUNNING:-}" ]; then
  skip_nested "codex environment variable indicates nested execution"
fi

if [ -d "${HOME:-}/.codex/sessions" ] && [ ! -w "${HOME:-}/.codex/sessions" ]; then
  skip_nested "~/.codex/sessions is not writable from this sandbox"
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "FAIL: codex CLI not found" >&2
  exit 1
fi

mkdir -p "$SNAPSHOTS_DIR" "$(dirname "$PROJECT_FILE")"

codex exec --skip-git-repo-check --sandbox workspace-write --output-last-message "$CODEX_LAST_MESSAGE" <<PROMPT
You are Codex running a live research-context integration harness.

Create or overwrite this synthetic platform project file:
- ${PROJECT_FILE}

Use this frontmatter:
---
type: project
project: "${PROJECT}"
client: "_platform"
status: active
tags: [video, launch, ai, tooling, research-context-test]
---

Use this goal:
Plan a launch video for an AI developer-tool product using current 2026 references, Remotion, Codex CLI, Anthropic/OpenAI launch patterns, and current best practices.

Then read skills/research-context.md and run it literally for:
- project: ${PROJECT}
- client: _platform
- goal: Plan a launch video for an AI developer-tool product using current 2026 references, Remotion, Codex CLI, Anthropic/OpenAI launch patterns, and current best practices.
- project_file_path: ${PROJECT_FILE}
- snapshots_path: ${SNAPSHOTS_DIR}
- trigger_reason: live-integration
- model_cutoff: 2026-01

Write the final research-context snapshot exactly here:
- ${OUT}

Also write the budget ledger and self-check JSON under ${SNAPSHOTS_DIR}.
The output must include all five required category headings, a Claim Ledger table, total_websearch, total_webfetch, and low_confidence frontmatter.
Do not use paid X API or browser login.
PROMPT

status=$?
if [ "$status" -ne 0 ]; then
  echo "FAIL: codex exec exited $status" >&2
  exit 1
fi

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

[ -f "$OUT" ] || fail "output file missing: $OUT"
grep -Fq "subtype: research-context" "$OUT" || fail "output missing subtype"
grep -Fq "Recent launches in genre" "$OUT" || fail "missing Recent launches heading"
grep -Fq "Current tool/library versions" "$OUT" || fail "missing versions heading"
grep -Fq "Deprecated patterns" "$OUT" || fail "missing deprecated heading"
grep -Fq "New capabilities since cutoff" "$OUT" || fail "missing capabilities heading"
grep -Fq "Current best practices in domain" "$OUT" || fail "missing best practices heading"
grep -Fq "Claim Ledger" "$OUT" || fail "missing Claim Ledger"
grep -Fq "total_websearch:" "$OUT" || fail "missing total_websearch"
grep -Fq "total_webfetch:" "$OUT" || fail "missing total_webfetch"
grep -Eq "low_confidence: (true|false)" "$OUT" || fail "missing low_confidence frontmatter"
grep -Eq "RC-[0-9]{3}" "$OUT" || fail "missing claim IDs"
if grep -Eiq "paid X API|browser login" "$OUT"; then
  fail "output mentions disallowed research path"
fi

CLAIM_COUNT="$(grep -Eo "RC-[0-9]{3}" "$OUT" | sort -u | wc -l | tr -d ' ')"
if [ "$CLAIM_COUNT" -lt 3 ]; then
  fail "expected at least 3 distinct claim IDs"
fi

POST_CUTOFF_COUNT="$(grep -Eo "2026-(02|03|04|05|06|07|08|09|10|11|12)-[0-9]{2}" "$OUT" | sort -u | wc -l | tr -d ' ')"
if [ "$POST_CUTOFF_COUNT" -lt 3 ]; then
  fail "expected at least 3 distinct post-cutoff citation dates"
fi

ls "${SNAPSHOTS_DIR}"/*research-context-budget*.json >/dev/null 2>&1 || fail "budget ledger missing"
ls "${SNAPSHOTS_DIR}"/*research-context-check*.json >/dev/null 2>&1 || fail "self-check JSON missing"

echo "PASS: live research-context synthetic project produced ${OUT}"
exit 0
