# Tool Discovery MCP

Planning-time tool survey and execution-time evidence capture for OneShot's Tool Lifecycle patch.

## Purpose

The MCP answers: given a load-bearing capability, the operator's quality bar, and a structured constraint envelope, which tools are fit for the bar and which constraints do they violate?

Stage 1 reads the canonical catalog, merges per-client overlays, writes vault-local operator curation/planning evidence, and returns planning evidence. Stage 2 adds overlay-scoped execution evidence recording for Tool-Fit Retrospectives. Neither stage acquires tools, spends money, mutates `.mcp.json`, or promotes overlay evidence into the canonical catalog without operator review.

## Tools

| Tool | Stage | Description |
|---|---|---|
| `survey_tools` | Stage 1 | Rank catalog tools for a capability + bar + constraints. |
| `get_tool` | Stage 1 | Return a full catalog entry, merged with a client overlay when provided. |
| `list_capabilities` | Stage 1 | List capability IDs known to the catalog. |
| `propose_refresh` | Stage 1 | Return a refresh proposal diff without writing the canonical catalog. |
| `record_operator_curation` | Stage 1 | Write a per-client operator-curated overlay entry. |
| `record_planning_evidence` | Stage 1 | Write planning-time fitness evidence under the client overlay evidence area. |
| `record_execution_evidence` | Stage 2 | Write Tier 1/2/3 execution evidence under `tools-catalog-overlay/evidence/{project_slug}/execution/`; canonical promotion remains operator-gated. |

Acquisition, spend reservation/capture, OAI-SPEND routing, and `.mcp.json` mutation are intentionally absent through Stage 2.

## Response Schemas

OAI-PLAN responses continue to validate against `schemas/oai-plan-response.schema.json`. Stage 2 adds the sibling `schemas/oai-tool-response.schema.json` rather than generalizing OAI-PLAN so execution-time Tool-Fit Retrospectives can evolve independently while reusing the same decision authorization and tool-presence canary block shape.

## Catalog

Canonical entries live in:

```bash
vault/archive/tools-catalog/
```

Optional per-client overlays live in:

```bash
vault/clients/{client_slug}/tools-catalog-overlay/
```

Schemas:

- `schemas/tools-catalog-entry.schema.json`
- `schemas/tools-catalog-overlay.schema.json`
- `schemas/tool-survey.schema.json`
- `schemas/oai-tool-response.schema.json`

## Setup

```bash
pip install -r vault/clients/_platform/mcps/tool-discovery/requirements.txt
python3 vault/clients/_platform/mcps/tool-discovery/server.py --check
```

## Opt-In Registration

`.mcp.template.json` includes a disabled template under `_commentedOutMcpServers`. Operators opt in by moving that entry under `mcpServers` in their local `.mcp.json` after the normal `register-mcp` review and approval flow.
