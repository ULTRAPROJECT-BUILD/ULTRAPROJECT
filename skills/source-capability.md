---
type: skill
name: source-capability
description: "The 5-tier sourcing skill — finds or builds MCPs, skills, and CLI harnesses from marketplace, GitHub, archive, CLI-Anything, or scratch"
inputs:
  - capability_type (required — "mcp" or "skill")
  - name (required — what the capability does, e.g. "Shopify inventory management")
  - domain (optional — industry/area, e.g. "e-commerce")
  - requirements (optional — specific features needed)
  - client (optional — client slug for client-scoped installation)
---

# Source Capability

You are the capability sourcer. Your job is to find or build the MCP server or skill file needed for a task. Always try to reuse before building from scratch.

## The 5-Tier Sourcing Cascade

```
Need: "{name}"
  → Tier 1: Search Skills marketplace (npx skills search)
    → Found and works? → USE IT, archive locally
    → Found but broken? → FIX IT, use it, archive the fixed version
  → Tier 1b (MCPs only): Search GitHub + MCP registries (WebSearch)
    → Found a repo? → Clone, install, test → USE IT, archive locally
    → Found but broken? → FIX IT, use it, archive the fixed version
  → Tier 2: Search internal vault/archive/
    → Found? → Copy, adapt (swap credentials, adjust config), test → done
  → Tier 2b: CLI-Anything harness (if tool already installed locally)
    → Wrap existing CLI/GUI into agent-controllable harness → test → archive
  → Tier 3: Build from scratch
    → Use build-mcp-server or build-skill skill → test → archive
```

**Practical expectation:** For Python FastMCP servers, Tier 3 (build from scratch) is the most common outcome. The Skills marketplace contains instruction-based Claude Code skills (not Python MCP servers), and GitHub repos typically use Node.js or heavy external service dependencies. Tier 1/1b are worth a quick check (~30 seconds) but should not delay the build decision. The fastest effective path is: Tier 2 (archive) → Tier 2b (CLI harness if tool is installed) → Tier 3 (build). (Learned from 2026-03-18-capability-sprint-sourcing-patterns, 2026-03-18)

## Process

### Tier 1: Marketplace Search

1. Search the Skills marketplace using the CLI:
   ```bash
   npx skills search "{capability name or keywords}"
   ```
   - Try exact name match first.
   - Then try keyword variants (e.g., "shopify" → "shopify inventory", "shopify orders", "shopify api").
   - Review the results: name, install count, and URL.
   - Note the **install count** from the search results — this is a pre-use quality signal.
   - If the skill links to a GitHub repo, check the **star count** via WebSearch or the repo page.

2. If a relevant match is found:
   a. Install it:
   ```bash
   npx skills add {owner/repo@skill} --yes
   ```
   b. Read the installed skill file to understand what it provides.
   c. Run [[test-mcp-server]] (for MCPs) or validate the skill file (for skills).
   d. **If it works:** proceed to Archive step.
   e. **If it's broken or close but needs fixes:**
      - Identify what's wrong (missing dependency, API change, bug).
      - Fix the code.
      - Re-test.
      - Proceed to Archive step (archive the FIXED version so future users get the working one).

3. If no match found on marketplace, proceed to Tier 1b (for MCPs) or Tier 2 (for skills).

**Note:** Do NOT try to browse https://skillsmp.com/ directly — the website blocks automated requests. Always use the `npx skills` CLI.

### Tier 1b: MCP Registry & GitHub Search (MCPs only)

If the needed capability is an MCP server and wasn't found in the Skills marketplace:

1. **Search for existing MCP servers** using WebSearch:
   ```
   Search: "{name} MCP server" OR "{name} model context protocol" site:github.com
   ```
   Also try:
   - `mcp-{name}` or `{name}-mcp` as GitHub repo names
   - Check https://github.com/modelcontextprotocol/servers for official MCP servers
   - Check https://github.com/punkpeye/awesome-mcp-servers for community-maintained list

2. If a relevant MCP repo is found:
   a. Read the README to verify it does what's needed.
   b. Clone (read-only, do NOT install dependencies yet):
   ```bash
   git clone --depth 1 {repo_url} /tmp/mcp-{name}
   ```
   c. **Security review BEFORE installing or running anything:**
   ```
   codex exec "Security audit /tmp/mcp-{name}/. Check all source files for: network calls, filesystem access, env var reads, eval/exec/subprocess, install hooks in package.json/setup.py. Verdict: PASS / FAIL."
   ```
   - **FAIL:** delete the clone, do NOT install. Document why and try Tier 2/3 instead.
   - **PASS:** proceed to install.
   d. Install dependencies: `cd /tmp/mcp-{name} && pip install -r requirements.txt` (or `npm install`).
   e. Copy the server code to the target location. For client project sourcing: `vault/clients/{client}/mcps/{name}/`. For grow-capabilities sourcing: `vault/clients/_platform/mcps/{name}/` — never to client directories.
   f. Run [[register-mcp]] (which runs its own security review as a second gate).
   g. Run [[test-mcp-server]] to validate.
   h. **If it works:** proceed to Archive step via [[archive-capability]].
   i. **If it needs fixes:** fix, re-test, re-review, proceed to Archive.

3. If no existing MCP found, proceed to Tier 2.

### Tier 2: Internal Archive Search

1. Read `vault/archive/_index.md` for the searchable catalog.
2. Search by:
   - Capability name/description
   - Domain/industry tags
   - Required features
3. If a match is found:
   a. Copy the archived capability to the target location:
      - Client-scoped (when sourcing for a specific client project): `vault/clients/{client}/mcps/{name}/` or `vault/clients/{client}/skills/`
      - Platform-scoped: `vault/clients/_platform/mcps/{name}/`
      - **grow-capabilities sourcing:** Always write to `vault/clients/_platform/mcps/` or `vault/archive/`, NEVER to client-scoped directories. grow-capabilities must not modify client data.
   b. Adapt: update configuration (API keys, endpoints, client-specific settings).
   c. Test via [[test-mcp-server]] or manual validation.
   d. If it works: done.
   e. If it needs fixes: fix, test, update the archive with the improved version.

4. **Quality ranking:** If multiple archive matches exist for the same capability, rank them by:
   - **Score** (QC pass rate) — higher is better. This is the primary signal once the agent has usage data.
   - **Uses** — more uses = more battle-tested
   - **Last QC date** — more recent = still working
   - **Community signals** — `marketplace_installs` and `github_stars` from the archive entry. Higher = more community trust. These matter most for capabilities with zero internal Uses (never tried by the platform yet).
   - **Source tier** — marketplace/github > archive adaptation > scratch
   Pick the highest-ranked match. If the top match has a Score below 0.5 (fails QC more than half the time), consider Tier 3 instead.

6. **A/B test (optional — when a new competitor appears):** If a newly sourced capability (from marketplace or GitHub) competes with an existing archive capability for the same function:
   a. Run a lightweight A/B test: execute the same representative task with both capabilities.
   b. Run [[quality-check]] on both outputs.
   c. Compare: QC verdict, output quality, completeness, execution time.
   d. Keep the winner as the primary archive entry. Demote the loser (add a note: "Lost A/B test to {winner} on {date} — {reason}").
   e. Only do this once per competitor pair, not on every project. The result is recorded in the archive index so future sourcing skips the loser.
   f. Skip A/B testing if the existing capability already has a Score above 0.9 (proven excellent) — don't waste tokens challenging something that's already working great.

5. **Domain match check:** Before reusing any MCP or skill from the archive, verify its output domain matches the target client's industry. A landscape 3D MCP cannot produce coffee shop imagery regardless of overlay tricks. If the domain doesn't match, skip to Tier 3 or omit the capability and note the gap. (Learned from 2026-03-17-wrong-blender-scene-reused, 2026-03-17)

6. **Nonprofit data source hierarchy (known):** For nonprofit data requests, skip generic API searches and use this proven hierarchy:
   - **Tier 1a: IRS BMF CSV** — free, stdlib-only Python, covers all ~1.8M US exempt orgs. Provides identity, classification, financials. No URLs, phones, or contacts. Download from `https://www.irs.gov/pub/irs-soi/eo_{state}.csv`.
   - **Tier 1b: IRS Form 990 XML e-filings** — free, covers ~30% of nonprofits (e-filers only). Provides website URLs (~15% of all orgs), phone numbers (~27%), contact names (~27%). Technical notes: uses Deflate64 compression (Python zipfile cannot handle it, use system `unzip`); XML namespaces vary, use local-name matching.
   - **Tier 1c: ProPublica Nonprofit Explorer API** — free, but provides ONLY filing data and PDF links. Does NOT return website URLs, phone numbers, email addresses, or contacts. Do not use ProPublica for enrichment.
   - **Tier 2: GuideStar/Candid API** — paid subscription, best coverage for URLs/phones/contacts.
   - **Tier 3: Google Custom Search API** — paid per query, can find websites but expensive at scale.
   - For nonprofit data, the BMF pipeline is stdlib-only Python (csv, json, urllib) — no MCPs or pip dependencies needed. Build scripts with `--state` flag for any US state. (Learned from 2026-03-18-irs-990-xml-enrichment-strategy, 2026-03-18-irs-bmf-pipeline-pattern, and 2026-03-18-propublica-no-website-urls, 2026-03-18)

7. **Blender headless scripting (known capability):** For any project needing 3D assets beyond landscape scenes (game models, product visualizations, architectural components, characters, weapons, etc.), Blender headless Python scripting (`blender --background --python script.py`) is a proven platform capability. The Blender MCP is appropriate only when its specific tools match the domain (landscapes, vegetation). For everything else, write custom Python scripts targeting the `bpy` API. This approach generated 106 unique 3D models (.glb) in ~12 minutes using bmesh operations and primitive geometry. Archive Blender Python scripts as reusable patterns for "headless 3D asset generation." (Learned from 2026-03-18-blender-headless-scripting-unlocks-3d-asset-pipeline, 2026-03-18)

8. **Single-file Flask dashboard pattern (known capability):** For platform tools that need a web UI (dashboards, admin panels, status pages), the proven pattern is: single Flask file with embedded HTML/CSS/JS, JSON API endpoint for data, JS `fetch()` polling for live refresh, server-side SVG generation for charts, CSS custom properties for dark/light theming, CSS Grid for responsive layout. Zero dependencies beyond Flask. This pattern scaled to ~2,700 lines with 9 data panels. (Learned from 2026-03-18-dashboard-v2-single-file-rewrite, 2026-03-18)

9. If no match in archive, proceed to Tier 3.

### Tier 2b: CLI-Anything Harness (before building from scratch)

**Before writing a full MCP from scratch, check if the tool already has a CLI or GUI that can be wrapped.** The `cli-anything` skill (archived at `vault/archive/skills/cli-anything.md`) generates a structured CLI harness for ANY software — Blender, GIMP, FFmpeg, Godot, LibreOffice, or any tool with a command-line interface or Python API.

This is faster than building a full MCP and produces a CLI the agent can invoke directly via Bash. Use this when:
- The tool already exists on the system (e.g., `blender`, `godot`, `ffmpeg`, `soffice`)
- You need basic automation (run commands, pass arguments, get structured output)
- A full MCP with tool definitions would be overkill

Skip this if you need bidirectional real-time communication (MCP is better for that).

### Tier 3: Build from Scratch

1. **For MCPs:** Use the [[build-mcp-server]] skill.
   - Provide: name, description, required tools, API documentation.
   - The skill will generate a Python MCP server following the platform template.
   - **Output location:** For client project sourcing, write to `vault/clients/{client}/mcps/{name}/`. For grow-capabilities sourcing, write to `vault/clients/_platform/mcps/{name}/` — never to client directories.

2. **For Skills:** Use the [[build-skill]] skill.
   - Provide: name, description, inputs, process steps.
   - The skill will generate a markdown skill file following the platform schema.
   - **Output location:** Always `vault/archive/skills/` or `vault/clients/{client}/skills/`. Never `skills/*.md` (platform skills are admin-only).

3. Test the result via [[test-mcp-server]] or manual validation.

### Archive Step (Always)

After successfully sourcing or building a capability, ALWAYS run [[archive-capability]]:
- Strips client-specific data, API keys, credentials.
- Saves a sanitized copy to `vault/archive/mcps/` or `vault/archive/skills/`.
- Updates `vault/archive/_index.md`.
- This ensures the next time this capability is needed, Tier 2 finds it instantly.

## Registration

For MCPs, after sourcing/building, run [[register-mcp]] to add it to `.mcp.json` so Claude Code can use it.

## Decision Records

Write a decision record when:
- Choosing between multiple marketplace options
- Deciding to fix a broken marketplace skill vs building from scratch
- Choosing Tier 3 over a partially-matching Tier 2 result

## Output

Return:
- **Tier used:** 1 (marketplace), 1b (GitHub), 2 (archive), 2b (CLI harness), or 3 (scratch)
- **Capability path:** where it was installed
- **Test results:** pass/fail summary
- **Archive status:** whether it was archived for future reuse
- **Fixes applied:** if a marketplace/archive skill was modified, what was changed

## The Compounding Effect

Every sourcing operation makes the platform faster:
- Marketplace skills get fixed and archived locally → next user gets the working version.
- Scratch-built tools get archived → next similar client gets instant setup.
- The archive grows with every client → Tier 2 hit rate increases over time.

## See Also

- [[test-mcp-server]]
- [[build-mcp-server]]
- [[build-skill]]
- [[archive-capability]]
- [[register-mcp]]
- [[orchestrator]]
