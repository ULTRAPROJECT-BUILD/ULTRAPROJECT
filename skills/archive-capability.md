---
type: skill
name: archive-capability
description: Strips credentials and client data from a built/fixed MCP or skill, saves sanitized version to archive
inputs:
  - source_path (required — path to the MCP directory or skill file to archive)
  - capability_type (required — "mcp" or "skill")
  - name (required — capability name)
  - description (required — what the capability does)
  - domain (optional — industry/area tags)
  - original_source (optional — "marketplace", "archive", "scratch", "github")
  - marketplace_installs (optional — install count from Skills marketplace at time of sourcing)
  - github_stars (optional — GitHub star count at time of sourcing)
  - client (optional — originating client slug, for de-identification logging)
---

# Archive Capability

You are archiving a capability (MCP server or skill file) for future reuse. This runs after every successful build, fix, or sourcing operation.

## Process

### Step 0: Verify Security Review Passed

**Do NOT archive any MCP or capability that hasn't passed a Codex security review.** Check the ticket work log for a "Security review: PASS" entry. If not found, run the review now via [[register-mcp]] Step 2. If FAIL, do not archive — create a fix task instead.

### Step 1: Read the Source

1. Read the source files:
   - **MCP:** read `server.py`, `requirements.txt`, `README.md` from `{source_path}/`.
   - **Skill:** read the single `.md` file at `{source_path}`.

### Step 2: Sanitize

Strip ALL of the following from the source code and documentation:

**Must Remove:**
- API keys, tokens, passwords, secrets (even if they look like placeholders)
- Client names, business names, personal names
- Email addresses (replace with `example@example.com`)
- Phone numbers (replace with `+1XXXXXXXXXX`)
- URLs pointing to specific client resources (replace with `https://example.com`)
- File paths containing client slugs (replace with `{client}`)
- Hardcoded IDs (database IDs, account IDs)
- IP addresses and specific hostnames

**Must Preserve:**
- All functional code and logic
- Environment variable references (e.g., `os.environ.get("API_KEY")`)
- Type hints and docstrings
- Error handling
- The overall architecture and approach
- Requirements/dependencies
- Generic configuration structure

**Replacement Rules:**
- API keys → `"YOUR_API_KEY_HERE"`
- Client names → `"{client_name}"`
- Specific URLs → `"https://api.example.com"`
- Email addresses → `"user@example.com"`
- Phone numbers → `"+1XXXXXXXXXX"`

### Step 3: Write to Archive

1. **MCP:**
   - Copy sanitized files to `vault/archive/mcps/{name}/`.
   - Include: `server.py`, `requirements.txt`, `README.md`.

2. **Skill:**
   - Copy sanitized file to `vault/archive/skills/{name}.md`.

### Step 4: Update Archive Index

1. Read `vault/archive/_index.md`.
2. Append a new entry:
   ```
   | {name} | {capability_type} | {description} | {domain} | {original_source} | {now} | 0 | 0 | — | 0.0 |
   ```
   The last four columns are quality metrics (initialized at zero):
   - **Uses** — how many times this capability has been used across projects
   - **QC passes** — how many times projects using this capability passed QC on first try
   - **Last QC** — date of most recent QC result
   - **Score** — quality score (QC passes / Uses, as a ratio 0.0–1.0)

   If the capability was sourced from the marketplace or GitHub, also record in the archive entry's metadata:
   - `marketplace_installs: {count}` — community adoption signal
   - `github_stars: {count}` — community quality signal
   These are point-in-time snapshots from when the capability was sourced. They inform initial trust ranking before the agent has its own usage data.
3. If an entry with the same name already exists:
   - Update the description, domain, source, and date (newer version replaces older).
   - **Preserve the quality metrics** — don't reset Uses/QC passes on update.
   - Add a note: "Updated {now} — {reason}".

### Step 5: Verify Sanitization

1. Re-read the archived files.
2. Search for common patterns that indicate unsanitized data:
   - Strings matching email patterns: `\b[\w.-]+@[\w.-]+\.\w+\b`
   - Strings matching phone patterns: `\+?\d{10,}`
   - Strings matching API key patterns: `sk_`, `rk_`, `pk_`, `api_`, long alphanumeric strings
   - Client slug references in file paths
3. If any are found, re-sanitize and overwrite.

### Step 6: Log

1. If `client` is provided, note in the client's work log that a capability was archived from their project (without revealing what — the archive is de-identified).
2. Write to the admin log: "{capability_type} '{name}' archived from {original_source} on {now}."

## Output

Return:
- **Archive path:** where the sanitized capability was saved
- **Sanitization status:** clean | warnings (list any suspicious patterns found)
- **Index updated:** true
- **Original source:** marketplace | archive | scratch
- **Domain tags:** applied tags

## Quality Feedback Loop

When a project completes and QC runs, the archive should be updated:

1. **After [[quality-check]] runs:** For each capability (MCP or skill) used in the project, update its archive index entry:
   - Increment **Uses** by 1
   - If QC verdict was PASS on first attempt, increment **QC passes** by 1
   - Update **Last QC** to today's date
   - Recalculate **Score** = QC passes / Uses

2. **After [[post-delivery-review]]:** If the review flags issues caused by a specific capability, add a note to that capability's archive entry describing the issue. This helps future agents decide whether to use or skip it.

3. **When multiple versions exist:** If the archive has two capabilities for the same function (e.g., `stock-analysis` and `stock-analysis-v2`), the agent should prefer the one with:
   - Higher Score (QC pass rate)
   - More Uses (battle-tested)
   - More recent Last QC date (still working)
   - If scores are tied, prefer the one from a higher Tier source (marketplace > archive > scratch)

This creates a natural selection process — capabilities that produce good results get used more, and ones that cause QC failures get deprioritized over time.

## The Compounding Effect

Every archived capability makes the platform faster:
- Next time [[source-capability]] needs something similar, Tier 2 finds it immediately.
- Fixed marketplace skills mean the next user gets a working version.
- The archive grows with every client, reducing Tier 3 (scratch) builds over time.

## Important

- NEVER archive files that still contain real credentials. The verification step (Step 5) exists specifically to catch this.
- The archive is meant to be reusable across clients. If it can't be generalized, it shouldn't be archived.
- Skills that are highly client-specific (e.g., "send weekly report to Jane at Acme Corp") should NOT be archived — only the generic pattern should be (e.g., "send scheduled report to client").

## See Also

- [[source-capability]]
- [[build-mcp-server]]
- [[build-skill]]
- [[archive-project]]
