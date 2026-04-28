# Build Instructions

You are operating **ULTRAPROJECT**, a self-bootstrapping chat-native agent platform. An operator starts work from Codex or Claude, the system figures out what the project needs, builds its own MCPs and skills when needed, then executes tasks autonomously through the vault.

## What's Built

The platform layer is ready for use: vault schema, orchestrator + executor skills, mechanical gates, routing runtime, per-project `status.md` artifacts, regression tests, and a starter set of MCP servers. It is shared as-is for personal/exploration use; see `README.md` for status and `SECURITY.md` for the threat model.

### Platform Infrastructure
- [[SYSTEM]] — system prompt for all agents (roles, rules, vault structure, safety)
- `vault/` — shared markdown memory with YAML frontmatter schema (see [[SCHEMA]])
- `vault/clients/` — workspace isolation layer (each project gets its own subdirectory) with `_template/`, `_platform/`, and `_registry.example.md` (copy to `_registry.md` on first install)
- `vault/archive/` — sanitized reusable capabilities with `mcps/`, `skills/`, `playbooks/`, `patterns/`
- `vault/config/` — platform config, metering, admin log, spending log
- `.mcp.example.json` — MCP server registry template (copy to `.mcp.json` on first install)

### MCP Servers (under `vault/clients/_platform/mcps/`)
- `spending/` — agent spending budget with caps (wallet protection)
- `stripe/` — optional Stripe rail (restricted key)
- Plus third-party API wrappers: `calendar`, `charity`, `color-scheme`, `computer-use`, `eventbrite`, `financial-datasets`, `google-maps`, `google-search-console`, `image-compare`, `imagegen`, `mlx-whisper`, `sec-edgar`, `semantic-search`, `webflow`

### Skills
- **Core:** [[orchestrator]], [[create-project]], [[create-ticket]], [[check-tickets]], [[check-projects]], [[run-orchestrator]]
- **Workspace lifecycle:** [[collect-payment]] (optional billing), [[delete-client-data]] (workspace cleanup)
- **Capability sourcing:** [[source-capability]], [[build-mcp-server]], [[register-mcp]], [[test-mcp-server]], [[build-skill]], [[archive-capability]]
- **Institutional knowledge:** [[archive-project]], [[match-playbooks]], [[consolidate-lessons]], [[post-delivery-review]]
- **Quality & craft:** [[creative-brief]], [[self-review]], [[quality-check]], [[deliverable-standards]]
- **System awareness:** [[gather-context]], [[vault-status]]

## Optional: Running as a Service

For personal use you can ignore this section. The defaults work out of the box. The pieces below only matter if you want to run ULTRAPROJECT as a billable service for other people:

1. Register an LLC → update `vault/config/platform.md` legal section
2. Get ToS + Privacy Policy reviewed by a lawyer
3. Host ToS and Privacy Policy at public URLs → update [[platform]] legal URLs
4. Set up Stripe → update `.mcp.json` with a restricted API key (only if you set `pricing.require_payment: true`)
5. Set up a pre-funded spending card if you want agents to spend money on third-party APIs

## Key Design Decisions

- **Workspace isolation:** Each project → `vault/clients/{slug}/` with its own tickets, snapshots, decisions, and deliverables
- **4-tier capability sourcing:** Skills marketplace → GitHub/MCP registries → internal archive → build from scratch
- **Self-building:** Agents write MCP server code, test it, register it, archive it
- **Self-improvement:** Internal platform projects use the same loop. Idle time only.
- **Optional payment rail:** Stripe (fiat). Work gates behind payment when `pricing.require_payment` is true. Off by default.
- **Financial safety is infrastructure-enforced:** Restricted API keys, optional pre-funded card with caps
- **Archive compounds:** Every build gets sanitized and archived → next project is faster

## Running the System

When writing or updating vault records, get timestamp values from the machine-local clock (`date +"%Y-%m-%dT%H:%M"` in the current system timezone). Do not infer them, and do not write UTC values as naive local times.

**Manual (development):**
```bash
cd /path/to/ULTRAPROJECT
claude -p "Read SYSTEM.md and skills/orchestrator.md — especially the Critical Rules block at the top of orchestrator.md, those are load-bearing. Follow the skill literally. Execute the orchestrator with this goal: 'your goal here'" --dangerously-skip-permissions
```

**Chat-native operation:** start, pause, and resume work directly from Codex or Claude. This clean distribution does not include always-on scheduled behavior.

## Environment Requirements

- Claude Code CLI (`claude` command) and/or Codex CLI (`codex` command)
- Python 3.9+ and pip
- Stripe account with restricted API key — only if you enable the optional payment rail

## See Also

- [[SYSTEM]]
- [[SCHEMA]]
- [[orchestrator]]
- [[platform]]
