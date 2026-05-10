---
type: skill
name: research-context
description: Proactive external research before project planning to mitigate training-cutoff gaps; writes a cited current-research snapshot with an audited WebSearch/WebFetch usage ledger.
inputs:
  - project (required - project slug)
  - client (optional - client slug; use _platform for platform-scoped client workspace projects)
  - goal (required - high-level project goal or project frontmatter goal)
  - project_file_path (required - absolute or repo-relative path to the project file)
  - snapshots_path (optional - output directory; derive from project_file_path when omitted)
  - trigger_reason (required - deterministic reason emitted by the orchestrator trigger)
  - model_cutoff (optional - default: 2026-01)
  - previous_snapshot_path (optional - latest prior research-context snapshot when refreshing)
  - force_refresh (optional - default false; true when stale snapshot is older than seven days)
---

# Research Context

Run this skill from [[project-plan]] Step 0 when the Research Context Trigger returns `required` or `refresh_required`. The output is a compact, cited `research-context.md` snapshot that gives project-plan and creative-brief current evidence about tools, vendors, references, launches, deprecated patterns, and best practices.

## Contract Boundary

Use Path C only: WebSearch through search-engine results and WebFetch only on selected result URLs. Do not use paid X API, unpaid direct X API, browser-driven X login, browser-driven vendor login, computer-use browsing through logged-in accounts, scraping behind authentication, scheduled crawlers, unofficial API keys, or paid search APIs.

Do not call WebSearch or WebFetch unless `scripts/research_context_budget.py reserve` records the call first. Reservations are an audit ledger, not a gate: `reserve` always allows valid category/kind calls and records each planned search/fetch so the operator can see actual cost and coverage afterward. The discipline is contractual; every search/fetch call still goes through the ledger even though the ledger does not deny calls.

The skill does not spawn a subagent. Research, synthesis, self-checking, and snapshot writing happen in the invoking context. If a future implementation adds a subagent, the full prompt template must be added inline here before use.

## Inputs

- `project`: canonical project slug from project frontmatter.
- `client`: optional client slug; `_platform` is valid for `vault/clients/_platform`.
- `goal`: original objective from the operator or project frontmatter.
- `project_file_path`: canonical project file created by [[create-project]]; read before searching.
- `snapshots_path`: output directory; derive from project location when omitted.
- `trigger_reason`: deterministic trigger output, such as `keyword:latest`, `tag:video`, `creative-brief-default`, or `latest_snapshot_stale`.
- `model_cutoff`: default `2026-01`; use it to frame "since cutoff" findings.
- `previous_snapshot_path`: optional prior research-context snapshot for refresh runs.
- `force_refresh`: true only when stale research is older than seven days.

## Step 1: Classify Project Domain

Read the project file first. Extract title, slug, client, goal, context, notes, tags, explicit tools, vendors, libraries, references, genre, and environment/tool inventory.

Classify:
- `domain`
- `deliverable_type`
- `genre`
- `primary_audience`
- `named_tools`
- `named_vendors`
- `named_libraries`
- `named_platforms`
- `named_references`
- `currentness_risks`

Classification rules:
- If the goal names "launch video", classify deliverable type as `video`.
- If the goal names "website", classify deliverable type as `frontend/web`.
- If the goal names "MCP", classify deliverable type as `developer-tooling`.
- If the goal names "deck", classify deliverable type as `presentation`.
- If the goal names "game", classify deliverable type as `game`.
- If no clear genre exists, set `genre: unknown` and research broad domain best practices.

Build a query plan with exactly five category blocks:
- Recent launches in genre
- Current tool/library versions
- Deprecated patterns
- New capabilities since cutoff
- Current best practices in domain

For each category, list the initial and likely follow-up WebSearch query strings, WebFetch candidate criteria after search results exist, expected source types, and high-signal result criteria. Do not perform network calls in Step 1.

## Step 2: Reserve Calls And Research

Initialize the ledger:

```bash
python scripts/research_context_budget.py init --ledger "{ledger_path}" --project "{project}" --categories "Recent launches in genre" "Current tool/library versions" "Deprecated patterns" "New capabilities since cutoff" "Current best practices in domain"
```

The `--websearch-per-category` and `--webfetch-per-category` arguments are legacy annotations only when present; they are not enforced. The ledger exists to show what was actually spent. It is not a call-count cap.

Before every search:

```bash
python scripts/research_context_budget.py reserve --ledger "{ledger_path}" --category "{category}" --kind WebSearch --query "{query}"
```

Before every fetch:

```bash
python scripts/research_context_budget.py reserve --ledger "{ledger_path}" --category "{category}" --kind WebFetch --url "{url}"
```

After each attempted call, record the result:

```bash
python scripts/research_context_budget.py record --ledger "{ledger_path}" --reservation-id "{reservation_id}" --status "{ok|zero_results|blocked|error|skipped}" --result-count "{count}" --url "{url_or_empty}"
```

Reservation JSON includes `allowed: true` and `reservation_id` for every valid reservation. A reserved call counts as used even if the later network call fails.

Research each category until the project's questions in that category are genuinely answered. The skill's own self-judgment governs completion:
- every named tool, vendor, library, and platform has a verified current state or an explicit `[INFERRED:]` explanation for why the current state could not be directly verified
- every architecture decision the brief or plan will lean on has been checked against current evidence
- deprecated-pattern coverage exists for the project's chosen tools, vendors, libraries, platforms, and deliverable type
- thin or blocked evidence is named honestly instead of converted into factual absence

Fixed category order:
1. Recent launches in genre
2. Current tool/library versions
3. Deprecated patterns
4. New capabilities since cutoff
5. Current best practices in domain

Query examples:
- Recent launches: `"{genre}" "launched" "2026" site:x.com`
- Recent launches: `"{genre}" "show HN" "2026" site:news.ycombinator.com`
- Versions: `"{library}" "release" "2026" site:github.com`
- Versions: `"{framework}" "release notes" "2026"`
- Deprecated patterns: `"{library}" deprecated "2026"`
- Deprecated patterns: `"{framework}" migration guide deprecated "2026"`
- New capabilities: `"{vendor}" "new capability" "2026"`
- New capabilities: `"{domain}" "now supports" "2026"`
- Best practices: `"{domain}" best practices 2026`
- Best practices: `"{deliverable_type}" "best practices" "2026"`

Adapt queries to the project. If Remotion is named, query Remotion releases and practices first. If Anthropic Computer Use is named, query Anthropic announcements and indexed social launch threads first. If "launch videos" is named, query recent AI launch videos, product video references, and vendor launches. Do not waste calls on broad generic topics when named tools or vendors exist.

## Incremental Summarization

Avoid retaining raw hit lists in context. For each category:

1. Run a reserved search.
2. Review only titles, URLs, snippets, and dates.
3. Reserve fetches only for high-signal URLs.
4. Fetch the pages needed to answer the category's project questions.
5. Append a compact category digest immediately.
6. Discard raw hit lists after extracting claim candidates.

Working files:
- `{snapshots_path}/{date}-research-context-working-{project}.md`
- `{snapshots_path}/{date}-research-context-budget-{project}.json`

Per search, append query string, call kind, result count, top candidate URLs, and selection or skip reason. Per fetched URL, append source title, URL, publication date or observed date, 2 to 4 source digest bullets, and candidate claims. Do not paste full articles, full X threads, or full HN discussions.

## Step 3: Synthesize Findings

Produce per-category findings:
- enough findings to answer the category's project questions when evidence exists
- a concise evidence-limit note when evidence is thin
- A `No strong current evidence found after current-source checks.` note when the category remains thin.
- Project implications for project-plan and creative-brief.

Every finding is a claim. Every claim must have a claim ID, category, claim text, URL plus citation date within last 12 months, or explicit `[INFERRED: ...]`, confidence (`high`, `medium`, or `low`), and project implication.

Cited claim format:

```markdown
- **RC-001:** {claim}. ([{source title}, YYYY-MM-DD]({url}))
  **Implication:** {what project-plan or creative-brief should do with it}
```

Inferred claim format:

```markdown
- **RC-009:** {claim}. [INFERRED: {basis; name cited facts or missing direct evidence}]
  **Implication:** {downstream assumption or risk}
```

Rules:
- If there is no URL, the claim is `[INFERRED:]`.
- If there is no date, the claim is `[INFERRED:]`.
- If the date is older than 12 months from machine-local today, the claim is `[INFERRED:]` unless another fresh source supports it.
- Search-snippet-only claims caused by blocked WebFetch are `low` confidence.
- Do not state absence as fact unless strongly cited.
- Absence from search results is not a factual claim.

## Step 4: Self-Check

Run the checker before emitting the final snapshot:

```bash
python scripts/check_research_context.py --snapshot "{working_snapshot_path}" --ledger "{ledger_path}" --today "{today}" --max-source-age-days 366 --max-inferred-ratio 0.30 --markdown-out "{snapshots_path}/{date}-research-context-check-{project}.md" --json-out "{snapshots_path}/{date}-research-context-check-{project}.json"
```

Set `{today}` from the machine-local date before running the check (`date +%Y-%m-%d` on macOS/Linux/WSL, `Get-Date -Format "yyyy-MM-dd"` in PowerShell, or an equivalent local Python date command).

The checker verifies cited claims include URL and date, cited dates are within last 12 months, the reservation ledger exists, non-inferred claims are not uncited, and claim IDs are well-formed. It sets `low_confidence: true` when inferred claims divided by all claims is more than 30 percent. `low_confidence: true` is not a checker failure; it is a warning that downstream skills must convert currentness claims into assumptions or open questions.

If the checker fails, revise the working snapshot and re-run the checker. Do not emit the final snapshot until it passes.

## Step 5: Write Snapshot

Final output path:
- Client-scoped: `vault/clients/{client}/snapshots/{project}/{date}-research-context-{project}.md`
- Platform client workspace: `vault/clients/_platform/snapshots/{project}/{date}-research-context-{project}.md`
- Legacy platform: `vault/snapshots/{project}/{date}-research-context-{project}.md`

Final frontmatter:

```yaml
---
type: snapshot
subtype: research-context
title: "Research Context - {project title}"
project: "{project}"
client: "{client or _platform}"
captured: {now}
agent: research-context
trigger_reason: "{trigger_reason}"
model_cutoff: "2026-01"
research_window_months: 12
domain: "{domain}"
deliverable_type: "{deliverable_type}"
genre: "{genre}"
total_websearch: {count}
total_webfetch: {count}
per_category_websearch_count:
  "Recent launches in genre": {count}
  "Current tool/library versions": {count}
  "Deprecated patterns": {count}
  "New capabilities since cutoff": {count}
  "Current best practices in domain": {count}
per_category_webfetch_count:
  "Recent launches in genre": {count}
  "Current tool/library versions": {count}
  "Deprecated patterns": {count}
  "New capabilities since cutoff": {count}
  "Current best practices in domain": {count}
cited_claim_count: {count}
inferred_claim_count: {count}
inferred_claim_ratio: {decimal}
low_confidence: {true|false}
budget_ledger: "{ledger_path}"
self_check_json: "{check_json_path}"
tags: [research-context, external-research, currentness]
---
```

Required final sections:
- `Research Scope`
- `Budget Ledger`
- `Executive Synthesis`
- `Recent launches in genre`
- `Current tool/library versions`
- `Deprecated patterns`
- `New capabilities since cutoff`
- `Current best practices in domain`
- `Claim Ledger`
- `Low-Confidence Handling`
- `Downstream Use`
- `Self-Check`

Claim ledger table columns:
- Claim ID
- Category
- Claim
- Citation URL
- Citation Date
- Status
- Confidence
- Implication

## Downstream Use

If `low_confidence: false`, cited claims may inform planning inputs. If `low_confidence: true`, currentness claims are hypotheses. Low-confidence claims must become Assumption Register rows or Open Questions. Creative briefs may cite low-confidence claims only as risks or assumptions unless independently verified.

Research-context does not replace the Executability Audit. It gives the audit fresh candidate facts to check. A claim that a capability exists does not prove the capability is available in this run. Deprecated-pattern findings should influence anti-patterns and planning choices.

## Error Handling

- WebSearch zero results: record `zero_results`, try the next useful query in the same category, and do not infer absence from one zero-result query.
- WebSearch error: record `error`, retry with a narrower query when that is likely to answer the category, and mark category confidence low if search remains unavailable.
- WebFetch blocked: record `blocked`, use title/snippet/date only if specific enough, mark snippet-only claims low confidence, and use `[INFERRED:]` if no date exists.
- Source dates conflict: prefer official vendor docs, releases, changelogs, or GitHub releases over social posts; preserve the conflict in source notes and use conservative implications.

## See Also

- [[orchestrator]]
- [[project-plan]]
- [[creative-brief]]
