---
type: skill
name: build-skill
description: Creates new domain-specific skill files from scratch
inputs:
  - name (required — skill name, kebab-case)
  - description (required — what the skill does)
  - inputs (required — list of input parameters with types and descriptions)
  - process (required — high-level steps the skill should follow)
  - domain (optional — industry/area context)
  - client (optional — client slug for client-scoped placement)
---

# Build Skill

You are creating a new skill file — a markdown instruction document that tells agents how to perform a specific task.

## Output Location

- **Client-scoped:** `vault/clients/{client}/skills/{name}.md`
- **Archive (for grow-capabilities):** `vault/archive/skills/{name}.md`
- **Platform-scoped (`skills/*.md`):** ADMIN ONLY. The autonomous system must NEVER write to `skills/*.md`. Platform skills are maintained by the admin in collaboration sessions. If the system needs a new platform skill, log it as a lesson note for the admin. This restriction prevents the autonomous system from modifying its own behavioral instructions.

## Skill File Template

```markdown
---
type: skill
name: {name}
description: {description}
inputs:
  - {param1} ({required|optional} — {description})
  - {param2} ({required|optional} — {description}, default: {value})
---

# {Title Case Name}

{One-sentence summary of what this skill does and when to use it.}

## Process

### Step 1: {First Step Title}

{Detailed instructions for step 1.}

### Step 2: {Second Step Title}

{Detailed instructions for step 2.}

...

## Output

Return:
- {what the skill produces}
- {status information}

## Error Handling

- {how to handle common failures}
```

## Build Process

### Step 1: Understand the Domain

1. Read the `process` input to understand what this skill needs to accomplish.
2. If `domain` is provided, consider domain-specific conventions and terminology.
3. If similar skills exist in `skills/` or `vault/archive/skills/`, read them for style consistency.

### Step 2: Design the Process

1. Break the high-level process into discrete, numbered steps.
2. Each step should be:
   - **Specific** — an agent can follow it without guessing.
   - **Observable** — the agent knows when the step is complete.
   - **Recoverable** — includes what to do if the step fails.
3. Identify which other skills or MCPs this skill depends on.
4. Identify what vault files this skill reads from or writes to.

### Step 3: Define Inputs and Outputs

1. List all input parameters with:
   - Name (kebab-case)
   - Required or optional
   - Type (string, list, dict, etc.)
   - Default value (if optional)
   - Description
2. Define the output — what the skill returns when complete.

### Step 4: Write Error Handling

1. For each step, identify what can go wrong.
2. Write recovery instructions:
   - Retry logic (if applicable)
   - Fallback behavior
   - When to escalate (create a ticket assigned to human)

### Step 5: Write the File

1. Use the template above.
2. Follow the YAML frontmatter schema from [[SCHEMA]].
3. Use imperative mood for instructions ("Read the file", not "You should read the file").
4. Include examples where they clarify the process.

### Step 6: Validate

1. Read the generated skill file.
2. Verify:
   - Frontmatter is valid YAML.
   - All inputs are documented.
   - Process steps are numbered and clear.
   - Output section exists.
   - Error handling section exists.
3. Check for references to other skills/MCPs — verify they exist.
4. Verify the skill includes a `## See Also` section linking to related skills.
5. **Post-build URL validation:** If the generated skill or its output references any external URLs (CDN libraries, APIs, data sources), verify each URL returns HTTP 200 before declaring the build complete. Build agents hallucinate library version numbers; an invalid CDN URL produces a deliverable that shows a blank page. (Learned from 2026-03-18-qc-pipeline-catches-cdn-version-bugs, 2026-03-18)

## Quality Criteria

A good skill file:
- Can be followed by an agent with NO prior context beyond SYSTEM.md.
- Doesn't assume knowledge not in the vault.
- Has clear entry and exit conditions.
- Handles the happy path AND failure modes.
- References specific file paths (not vague "the config file").
- Uses consistent terminology with other skills in the system.

## Output

Return:
- Skill file path
- Skill name
- Number of process steps
- Dependencies on other skills/MCPs
- Any warnings or notes

## See Also

- [[SCHEMA]]
- [[source-capability]]
- [[archive-capability]]
