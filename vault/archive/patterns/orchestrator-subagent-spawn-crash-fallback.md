---
type: pattern
title: "Creative-brief subagent spawn crash → spawn via agent_runtime.py spawn-task"
created: 2026-05-04T19:00
updated: 2026-05-05T08:30
tags: [orchestrator, reliability, fallback, subagent-spawn, creative-brief]
applies_to: any project running the OneShot orchestrator skill in chat-native mode
status: validated
---

# Creative-brief subagent spawn crash → spawn via `agent_runtime.py spawn-task`

## Symptom

Orchestrator's host CLI shows "Something went wrong / The session stopped responding" at or shortly after the moment it dispatches a subagent for a `task_type: creative_brief` ticket. The bug is intermittent and is not phase-bounded. The parent session emits the spawn request, but the parent never receives the final tool result from the worker.

> **Diagnostic correction (2026-05-05):** earlier revisions of this doc assumed the worker never started. That heuristic was too coarse. Diagnose future incidents from the worker's own host log, not only from the parent session log.

## Workaround

Route the build executor through `python3 scripts/agent_runtime.py spawn-task ...` invoked via the host's Bash tool with background execution enabled. The runtime forks a fresh, detached subprocess of the configured host CLI, which bypasses the failing native sidechain handoff. It also preserves ticket `in-progress` marking, executor logs, ledger writes, host-specific CLI flags, and clean process detachment.

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

## Command gotchas

- Do not silence stdout or stderr. Keep executor logs available for the ledger and operator review.
- Do not write directly to platform-owned files unless the orchestrator has routed the change through the appropriate platform workflow.

## Validation Notes

This pattern was retained as a generic reliability note for the OneShot orchestrator. The original reproduction details have been removed from the starter distribution because they referenced local sessions and prior project history. Future validation entries should use sanitized fixture identifiers and repository-relative paths only.

## Validated on

- Sanitized historical reproductions confirmed that `task_type: creative_brief` workers can fail intermittently when dispatched through the host's native sidechain primitive, while the detached `agent_runtime.py spawn-task` path preserves ledger and filesystem completion semantics.

## Scope of failure (important — do not over-generalize)

This is NOT "the orchestrator's subagent spawn is broken in general." Sanitized reproductions showed successful workers and failed creative-brief workers in the same operating window. The scope is `task_type: creative_brief` spawns generally, not a specific project, ticket, or phase.

The pattern is: **`task_type: creative_brief` subagents fail intermittently when spawned via the host's native sidechain primitive, regardless of phase.** Build executors can succeed while creative-brief workers fail, so treat this as a task-type-specific containment rule until a clean repro proves a narrower cause.

**Root cause remains unconfirmed.** Hypotheses worth investigating if a future ticket reproduces the pattern AND a clean repro is available:

- A specific token sequence in the spawn-prompt content (or in the resolved brief stack the executor reads) that triggers a parser/model edge case.
- A regression in the host CLI or the Anthropic/OpenAI API streaming path between the last successful spawn and the failing spawn.
- An interaction with cumulative deferred-tool schemas pulled during the parent session.

The fix in this doc is **containment, not diagnosis**. It routes around the unstable code path. Apply it as the default for `task_type: creative_brief` in chat-native mode. Continue using the orchestrator's normal native sidechain spawn for every other task type.

## See Also

- [[SYSTEM]]
- [[orchestrator]]
- [[creative-brief]]
