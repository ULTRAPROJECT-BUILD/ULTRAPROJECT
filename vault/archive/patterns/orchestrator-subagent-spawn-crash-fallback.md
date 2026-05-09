---
type: pattern
title: "Creative-brief subagent spawn crash → spawn via agent_runtime.py spawn-task"
created: 2026-05-04T19:00
updated: 2026-05-05T08:30
tags: [orchestrator, reliability, fallback, subagent-spawn, creative-brief]
applies_to: any project running the ULTRAPROMPT/OneShot orchestrator skill in chat-native mode (sister systems share skills/orchestrator.md and scripts/agent_runtime.py; fix applies to both)
status: validated
---

# Creative-brief subagent spawn crash → spawn via `agent_runtime.py spawn-task`

## Symptom

Orchestrator's host CLI (Claude Code or Codex) shows "Something went wrong / The session stopped responding" at or shortly after the moment it dispatches a subagent for a `task_type: creative_brief` ticket. The bug is intermittent and is not phase-bounded — it has been observed on master / Phase 1 / Phase 2 / Phase 3 brief writers across runs. The parent session's last assistant message is `stop_reason: tool_use` emitting the spawn — the dispatch *itself* succeeds. The subagent's own JSONL (under `~/.claude/projects/<project-dir>/<session-id>/subagents/agent-<id>.jsonl`, NOT in the parent JSONL) shows the subagent did start and ran for 2–5 minutes / 70–160 messages before its stream was cut. The subagent's last message has `stop_reason: null` and is truncated mid-output. The parent never received the final tool_result.

> **Diagnostic correction (2026-05-05):** earlier revisions of this doc said "the subagent never started," based on `grep -c '"isSidechain":true' <parent-session>.jsonl` returning 0. That heuristic was wrong — sidechain entries in Claude Code live in the `<session-id>/subagents/` subdirectory, not in the parent JSONL. To check whether a subagent ran, look for `~/.claude/projects/<project-dir>/<session-id>/subagents/agent-*.jsonl` and inspect the last assistant entry's `stop_reason` and `usage` block.

## Workaround

Route the build executor through `python3 scripts/agent_runtime.py spawn-task ...` invoked via the host's Bash tool with `run_in_background: true`. The runtime forks a fresh, detached subprocess of the host CLI (claude or codex), which bypasses the failing native sidechain handoff. It also preserves: ticket `in-progress` marking, executor logs, ledger writes, the proper CLI flag set per agent (claude: `-p --output-format stream-json --verbose --dangerously-skip-permissions`; codex: `exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --cd <cwd>`), and `stdin=DEVNULL` + `start_new_session=True` for clean detachment. See `scripts/agent_runtime.py:build_command` (line 3625) and `command_spawn_task` (line 4135).

This is normally forbidden by `skills/orchestrator.md` Critical Rule 1 in chat-native mode. The "Creative-brief subprocess exception" sub-bullet (added 2026-05-05) carves out exactly this case.

### Steps (orchestrator follows these mechanically)

1. **Resolve briefs and refresh project context** as you would for any executor (the existing `scripts/resolve_briefs.py` and `scripts/build_project_context.py` calls — the runtime's spawn-task path consumes the resulting context package the same way).

2. **Spawn via the Bash tool with `run_in_background: true`:**
   ```
   python3 scripts/agent_runtime.py spawn-task \
     --task-type creative_brief \
     --ticket-path "{ticket_path}" \
     --project "{project_slug}" \
     --client "{client_slug}" \
     --prompt "{executor_prompt}"
   ```
   Do NOT add a trailing shell `&` — the Bash tool kills shell-backgrounded children when its wrapper exits. Use the tool's own `run_in_background: true`. Do NOT redirect output to the null device — repo hooks block that token literally even inside heredocs (see Hooks gotchas).

3. **Monitor the ledger + on-disk state** as the completion signal. The completion contract is ALL of:
   - The executor ledger at `data/executors/{ticket-id}.json` (resolved by `scripts/agent_runtime.py:executor_ledger_path` — repo-root-relative, NOT under `vault/clients/`) reports `status: completed` (not `running` or `failed`). Stdout/stderr logs land at `logs/executors/{ticket-id}.stdout.log` and `logs/executors/{ticket-id}.stderr.log` per `executor_log_paths`.
   - The required deliverable file(s) exist at the paths the brief contract specifies.
   - Each deliverable is **size-stable** (no growth for ≥30 seconds) — guards against partial writes.
   - Ticket frontmatter is `status: closed` with `completed` set to a local-clock timestamp.
   - Project-file row is flipped from `- [ ]` to `- [x]`.
   - Mechanical pass: `python3 scripts/check_quality_contract.py --project-file ... --project-plan ... --brief <each brief path>` exits 0.
   - Ticket-specific checks per the brief contract — for verification-manifest tickets that means YAML parses, MD `total_rows` equals the YAML row count, and binding-source coverage holds.

4. **On completion**, the orchestrator's next step (typically: spawn the brief-gate reviewer via the standard native sidechain — gates are NOT affected by this exception) runs unchanged.

### Recovery on subprocess failure

- **Subprocess exits non-zero with no deliverables produced:** respawn once via the same `spawn-task` invocation. Wait until the first attempt's ledger has flipped to `failed` (and the subprocess has exited — check `child_pid`) before respawning, to avoid two concurrent processes mutating the same ticket.
- **Subprocess goes stale (no log growth for ≥10 minutes, ledger still `running`, child PID either dead or hung):** kill the child PID via `kill -TERM <pid>`, mark the ledger `failed`, then respawn once.
- **Subprocess produced PARTIAL deliverables (some files exist, some don't, or mechanical pass fails):** do NOT auto-respawn. Escalate to the operator with the partial-artifact paths, the executor's stdout/stderr log paths, and the ledger payload. A blind respawn risks clobbering or skipping the partial work depending on the executor's idempotency.

## Why this is sound

- The "subprocesses outside your chat that never return" property the chat-native prohibition was guarding against is exactly what we want for the route-around. The orchestrator polls disk; it doesn't need real-time chat output from the executor.
- `agent_runtime.py spawn-task` already does the bookkeeping (in-progress marking, work-log entries, ledger, stdout/stderr logs, heartbeat). Reimplementing that in skill prose was a worse plan and codex's review caught it.
- The deliverables are file-based, so the resumed orchestrator sees them as if a sidechain produced them. Brief-gate review (which still uses the native sidechain) is unaffected — it's a different prompt and a different session.
- Cross-context discipline is *more* preserved than via a sidechain: the executor runs in a completely fresh process with no parent session state.

## Hooks gotchas (this repo)

- `.claude/hooks/validate-bash.sh` blocks any bash command whose command line contains `>/dev/null` or `2>/dev/null` as literal text — including inside heredoc prompt content. Phrase any "do not silence output" instructions without those exact tokens. (e.g. "Do not redirect to the null device.")
- `.claude/hooks/restrict-paths.sh` blocks agent writes to `skills/`, `scripts/`, `vault/config/platform.md`, `.claude/hooks/`, `.claude/settings.json`, `.mcp.json`, `.env`, and `vault/config/.spending-integrity`. Skill changes (including this exception's wording in `skills/orchestrator.md`) require operator-applied edits.

## Cross-system provenance

OneShot is a sister system to ULTRAPROMPT and ships the same `skills/orchestrator.md` (verified byte-equivalent at the time of fix, modulo brand-string at line ~583) and the same `scripts/agent_runtime.py:build_command` path. The validation evidence below is from ULTRAPROMPT runs against `roster-app`. The fix is applied **prophylactically** to OneShot — once a creative-brief ticket lands cleanly via the new exception in OneShot, append a local validation entry under "Validated on" with the OneShot session id and project slug.

## Validated on

- **2026-05-04: roster-app, T-024 Phase 2 brief writer.** Two consecutive orchestrator sessions died at the same `tool_use` spawn step (sessions `6cb64d82-2225-4b80-a8ca-5d596b535ff8` and `cf5ef559-2cb8-4bd2-b014-ddb4feac7dcd` in `~/.claude/projects/-Users-michaelzola-Downloads-ULTRAPROMPT-main/`). Subagent JSONLs at `<session>/subagents/agent-*.jsonl` showed runs of 72 lines / ~2 min and 38 turns / peak input ~239K input tokens before death. Running T-024 as a fresh out-of-orchestrator `claude -p` produced a clean `check_quality_contract.py` PASS, 586-line brief, ticket closed, project-file checkbox flipped. Total elapsed ~13 min. (Note: that recovery was operator-driven raw-CLI; this doc now recommends `spawn-task` instead per codex's 2026-05-05 review — same fresh-subprocess property with full bookkeeping.)
- **2026-05-05: roster-app, T-035 Phase 3 verification manifest writer (also `task_type: creative_brief`).** Orchestrator session `03c05fba-01f3-44d2-9c98-ceaffb598e05` died at `stop_reason: tool_use` emitting the T-035 Agent spawn. Subagent JSONL `<session>/subagents/agent-ac791ee03bcbd11a3.jsonl` showed 163 lines / ~5 min runtime / peak input 335K tokens, last assistant message `stop_reason: null` truncated mid-thought as the executor was about to author the markdown manifest. No deliverables produced. Recovery via subprocess path is the test of this fix's effectiveness once the orchestrator skill carve-out lands.

## Scope of failure (important — do not over-generalize)

This is NOT "the orchestrator's subagent spawn is broken in general." Across the same project, **20+ prior subagent spawns succeeded**, including build executors at peak input tokens up to 554K (T-025 memory layer build) — far above where the failing brief writers died. T-005 (master brief) and T-006 (Phase 1 brief writer), also `task_type: creative_brief`, completed in this specific run at peaks 230K and 175K respectively — but the bug is intermittent and operator reports include master / Phase 1 brief failures in other runs. The scope is `task_type: creative_brief` spawns generally, not a specific phase.

The pattern is: **`task_type: creative_brief` subagents fail intermittently when spawned via the host's native sidechain primitive, regardless of phase.** Build executors at higher peak token counts worked. Tiny parent sessions (`cf5ef559` was 88 lines) failed identically to large ones (`6cb64d82` was 935 lines), so cumulative parent-session state is not the cause.

**Root cause remains unconfirmed.** Hypotheses worth investigating if a future ticket reproduces the pattern AND a clean repro is available:

- A specific token sequence in the spawn-prompt content (or in the resolved brief stack the executor reads) that triggers a parser/model edge case.
- A regression in the host CLI or the Anthropic/OpenAI API streaming path between the last successful spawn and the failing spawn.
- An interaction with cumulative deferred-tool schemas pulled via `ToolSearch` during the parent session — though `cf5ef559` argues against this since it was a tiny session.

The fix in this doc is **containment, not diagnosis**. It routes around the unstable code path. Apply it as the default for `task_type: creative_brief` in chat-native mode. Continue using the orchestrator's normal native sidechain spawn for every other task type.

## See Also

- [[SYSTEM]]
- [[orchestrator]]
- [[creative-brief]]
