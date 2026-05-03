---
type: skill
name: deep-execute
description: Handles complex tickets that require iterative, multi-pass execution with checkpointing
inputs:
  - ticket_id (required — the ticket being worked)
  - project (required — project slug)
  - client (optional — client slug)
---

# Deep Execute

You are working on a complex ticket that cannot be completed in a single pass. This skill provides a structured approach for iterative execution with checkpoints, allowing work to span multiple agent sessions.

**Rule: Always write a checkpoint before exiting. The next agent that picks up this ticket has no memory of your session — only the work log and artifacts you leave behind.**

## When to Use

This skill is used when a ticket has `complexity: deep` in its frontmatter. The orchestrator includes "Read skills/deep-execute.md" in the executor prompt for these tickets.

Tickets that typically need deep execution:
- Implementing a complex system (combat engine, physics, rendering pipeline)
- Building a multi-page website with custom functionality
- Creating a comprehensive research report with live data
- Any ticket where the work has 3+ distinct sub-steps that build on each other

## Process

### Step 1: Read Prior State

Before doing anything, check the ticket's work log for existing checkpoints:
- If **no checkpoints exist**: This is a fresh start. Proceed to Step 2.
- If **checkpoints exist**: Read the most recent checkpoint. It tells you:
  - What sub-steps are complete
  - What artifacts exist and where
  - What remains to be done
  - Any blockers discovered
  Resume from where the previous agent left off. Do NOT restart from scratch.

### Step 2: Decompose into Sub-Steps

If starting fresh, break the ticket into **3-7 internal sub-steps**. These are NOT separate tickets — they stay within this ticket's scope. Use short, concrete labels that will still make sense to the next agent reading the ticket. Write them to the work log:

```
- {now}: PLAN — Decomposed into {N} sub-steps:
  1. {sub-step 1 description}
  2. {sub-step 2 description}
  3. {sub-step 3 description}
  ...
```

Sub-steps should be ordered so each builds on the previous. Each sub-step should produce a verifiable artifact or state change.
Keep the labels stable across the life of the ticket. If you later realize the shape changed materially, append a revised `PLAN` entry before continuing instead of silently reusing old step numbers for different work.

### Step 3: Execute Sub-Steps

Work through sub-steps sequentially. For each sub-step:

1. **Do the work** — write code, generate content, build artifacts.
2. **Verify** — test what you just built. Does it work? Does it integrate with artifacts from previous sub-steps?
3. **Write a checkpoint** — after completing each sub-step (or if you're running low on time/context), write a checkpoint to the work log. Reuse the exact step number and keep the step label readable:

```
- {now}: CHECKPOINT — Sub-step {N}/{total} complete.
  State: {description of what exists and works}
  Artifacts: {paths to files created or modified}
  Verified: {what was tested and the result}
  Remaining: Sub-step {next}: {next step label}; ...
  Blockers: {any issues discovered, or "none"}
```

Good:
- `CHECKPOINT — Sub-step 2/5 complete (wire policy metadata + audit trail)`
- `Remaining: Sub-step 3: build violation corpus; Sub-step 4: run regression`

Bad:
- `CHECKPOINT — Sub-step 1/2 complete.`
- `Remaining: more work`

4. **Continue or exit** — evaluate after EVERY sub-step:
   - **Time check:** the runner uses progress-based timeouts: 30 minutes guaranteed, extends indefinitely if you're actively writing files (any file write resets the 10-minute inactivity timer), kills after 10 minutes of no file activity past the 30-min mark. Safety hard cap at 120 minutes (2 hours) per attempt. The runner watches ALL file types under vault/ (not just .md) — writing CSVs, HTML, images, checkpoints, or any deliverable counts as progress. Keep writing artifacts and checkpoints to stay alive.
   - **Context check:** if your conversation is getting long or you're losing track of earlier state, checkpoint and exit. A fresh agent with a clean context window will do better work.
   - **Progress check:** if you completed a meaningful unit of work (one state, one module, one section), checkpoint and exit. Shorter sessions with clean checkpoints are better than marathon sessions that stall.
   - **MANDATORY: write a checkpoint after EVERY sub-step.** This is not optional. The checkpoint is what keeps the runner from killing you (it sees file activity) and what lets the next agent resume. No checkpoint = lost work.
   - **Default behavior:** complete ONE sub-step per session, checkpoint, exit. Only continue to a second sub-step if the first was trivially small (< 2 minutes). When in doubt, checkpoint and exit — the next cycle starts in 5 minutes.

### Step 4: Completion

When all sub-steps are done:

1. Run a final verification — does the complete output work as a whole, not just individual pieces?
2. Write a final checkpoint:

```
- {now}: COMPLETE — All {N} sub-steps done.
  Final state: {what was produced}
  Artifacts: {all paths}
  Verification: {what was tested, results}
  Notes: {anything the reviewer should know}
```

3. If the project has a standalone Self-review ticket, link the artifacts and brief path in the work log for downstream review.
4. If NO standalone Self-review ticket exists, run [[self-review]] inline before closing.
5. Close the ticket.

## Exiting Mid-Work

If you cannot complete all sub-steps in this session:

1. **Write a checkpoint** with the current state (this is critical).
2. Set ticket status to `in-progress` (NOT `closed`, NOT `blocked`).
3. The orchestrator will see the `in-progress` status and spawn a new agent on the next cycle.
4. The new agent will read your checkpoint and continue.

**Do NOT:**
- Close the ticket if work remains
- Leave artifacts in a broken state — if sub-step 3 broke what sub-step 2 built, roll back to the sub-step 2 state before checkpointing
- Forget to list remaining sub-steps in the checkpoint

## Integration with Project Plan

If a project plan exists:
- Read the architecture decisions before starting. Your sub-steps must conform to them.
- After completing the ticket, the orchestrator will update the plan's artifact manifest with your outputs.

## Checkpoint Best Practices

- **Be specific about paths.** Don't say "the code file" — say `{workspace}/vault/clients/foo/deliverables/game/src/player.gd`.
- **Describe state, not process.** Don't say "I worked on the player controller." Say "Player controller exists at {path}, implements walk/jump/gravity, tested with arrow keys in Godot editor."
- **Note decisions made.** If you chose approach A over approach B during execution, note why. The next agent needs to understand your reasoning.
- **Flag risks.** If something works but feels fragile, say so. The next agent can address it.
- **Save output files as you go, not at the end.** If you're generating 5 CSVs, write each one to disk after completing it — not all 5 at the end. This serves two purposes: (1) completed files survive a timeout, and (2) the runner's progress detector sees file writes and extends your timeout. An agent that does all computation in memory and writes nothing to disk for 10+ minutes will get killed.
- **Check for existing output before starting.** Your first action should be checking what files already exist from a prior session. Skip completed work. This makes execution idempotent — running the same ticket twice doesn't duplicate effort.

## Error Handling

- If a sub-step fails and you can't fix it: write a checkpoint noting the failure, set ticket to `blocked`, and create a follow-up ticket describing the problem.
- If you discover the ticket's scope is larger than expected: write a checkpoint with what you've done, note the scope increase, and let the orchestrator decide whether to split the ticket.
- If architecture decisions seem wrong based on what you're learning: don't change them. Write a decision record explaining why they might need to change, and let the orchestrator handle the plan update.

## See Also

- [[orchestrator]]
- [[project-plan]]
- [[gather-context]]
- [[self-review]]
