---
type: skill
name: register-artifact-producer
description: Register a new artifact producer in the registry. Wraps an existing MCP, CLI tool, or API as a producer; runs synthetic fixture; promotes from pending to active when ready. Used during initial platform setup AND when a project's missing-producer-report requires a new registration.
inputs:
  - producer_id (required, canonical ID)
  - artifact_types (required, list)
  - producer_version (required, semver)
  - source_type (required, enum: existing_mcp|cli_tool|api_wrapper|new_mcp_via_source_capability)
  - mcp_path / cli_command / api_endpoint (one required)
  - api_key_env_var (optional)
  - applicable_mediums (required, list)
  - synthetic_fixture_path (required — what fixture proves the producer works)
  - license_acknowledgment_path (required)
  - fallback_chain (optional)
---

# Mission

Register an artifact producer in `vault/config/artifact-producers.md` so Visual Specifications can resolve artifact requests through the universal registry.

This skill is autonomous by default. Do not ask the operator for confirmation during the default flow. Operator override is allowed only when it was already supplied in the initial prompt and parsed by `scripts/parse_initial_prompt_directives.py`. If required inputs are missing, stop with a structured missing-input report instead of prompting.

The skill can be launched from either path:

- Initial platform setup, where the operator names the producer directly.
- A missing-producer report at `vault/snapshots/{project}/{date}-missing-producer-{artifact_type}.md`, where the operator has already chosen `register_existing` or `approve_build`.

V7-A does not auto-bootstrap producers. If `source_type` is `new_mcp_via_source_capability`, route through the existing `source-capability` and `build-mcp-server` flow as a separate capability task, then return here with the built wrapper path and fixture.

# Step 1 — Validate Inputs

Normalize the registration payload into one producer record with these fields:

```yaml
producer_id: example_imagegen
artifact_types: [photograph]
producer_version: 1.0.0
cli_command: "python3 tools/example-imagegen/produce.py"
state: pending
state_changed_at: "{machine-local timestamp}"
state_change_reason: "registered pending synthetic fixture validation"
quality_centroid_version: 0
last_synthetic_fixture_pass: "{machine-local timestamp}"
last_synthetic_fixture_status: never_run
rolling_success_rate_30d: 0.0
rolling_success_rate_90d: 0.0
total_invocations: 0
license_acknowledgment: vault/config/producer-licenses/example_imagegen.md
spend_per_artifact_estimate_usd: 0.0
fallback_chain: []
applicable_mediums: [web_ui]
```

Rules:

- `producer_id` is immutable and must match `^[a-z][a-z0-9_]*$`.
- Use exactly one invocation method: `mcp_path`, `cli_command`, or `api_endpoint`.
- `producer_version` must be semver, for example `1.0.0`, not `1.0`.
- `artifact_types` must use the closed V7-A type list: `photograph`, `illustration`, `icon_set`, `pattern_texture`, `product_3d`, `scene_3d`, `motion_graphics_loop`, `cinematic_video`, `ambient_audio`, `sfx`, `voiceover`, `live_prototype`, `data_chart`, `custom_typography`, `bespoke_typeface_variation`.
- `fallback_chain` defaults to `[]` when omitted.
- Use the machine-local clock for timestamp fields:

```bash
date +"%Y-%m-%dT%H:%M:%S%z"
```

Write the normalized record to a temporary JSON file under `/tmp` or the workspace cache, then validate it:

```bash
python3 - <<'PY'
import json
from pathlib import Path
import jsonschema

record_path = Path("PATH_TO_RECORD_JSON")
schema = json.loads(Path("schemas/artifact-producer.schema.json").read_text())
record = json.loads(record_path.read_text())
jsonschema.Draft202012Validator(schema).validate(record)
print("producer record schema valid")
PY
```

If validation fails, stop. Do not partially register the producer.

# Step 2 — Acquire Registration Lock

Register through the registry CLI. Do not edit `vault/config/artifact-producers.md` manually.

```bash
python3 scripts/artifact_registry.py register --record-json PATH_TO_RECORD_JSON
```

The CLI handles:

- Per-producer lock at `vault/locks/artifact-producers/{producer_id}.lock`.
- Idempotency: identical existing record returns no-op success.
- Conflict detection: same `producer_id` with different fields fails.
- Registry compare-and-swap using `last_updated` and content hash.
- Atomic write by temporary file plus rename.

If registration conflicts after the retry, stop with the conflict report. Do not ask for operator confirmation. The next run can retry with a fresh registry read.

# Step 3 — Run Synthetic Fixture

Place the synthetic fixture under the repository's test fixture tree, scoped to
the producer being registered.

The fixture should be the smallest proof that the producer wrapper works. Prefer
JSON fixtures when the wrapper needs explicit arguments:

```json
{
  "prompt": "Generate a 200x200 PNG of a flat red square on a transparent background.",
  "dimensions": "200x200"
}
```

If the wrapper requires a custom command for health checks, include `health_command` with placeholders:

```json
{
  "health_command": "python3 tools/example/health.py --fixture {fixture} --medium {medium} --artifact-type {artifact_type}",
  "prompt": "Generate a 200x200 PNG of a flat red square on a transparent background."
}
```

Run the health check:

```bash
python3 scripts/check_producer_health.py --producer-id PRODUCER_ID --json-out /tmp/producer-health.json
```

The health checker invokes every applicable medium for the producer's primary artifact type. It updates:

- `last_synthetic_fixture_pass`
- `last_synthetic_fixture_status`
- `rolling_success_rate_30d`
- `rolling_success_rate_90d`
- `total_invocations`

If the fixture fails, leave the producer in `pending`. The report in `/tmp/producer-health.json` is the evidence to fix the wrapper or fixture.

# Step 4 — Promote Pending To Active

A producer must pass at least three synthetic fixture invocations before use in production.

Run the health check until it has three successful invocations:

```bash
python3 scripts/check_producer_health.py --producer-id PRODUCER_ID --json-out /tmp/producer-health-1.json
python3 scripts/check_producer_health.py --producer-id PRODUCER_ID --json-out /tmp/producer-health-2.json
python3 scripts/check_producer_health.py --producer-id PRODUCER_ID --json-out /tmp/producer-health-3.json
```

`scripts/check_producer_health.py` promotes `pending -> active` when the producer has at least three consecutive successful synthetic fixture invocations.

If promotion must be performed manually after independently verified fixture evidence, use the registry state command:

```bash
python3 scripts/artifact_registry.py state \
  --producer-id PRODUCER_ID \
  --state active \
  --reason "promoted after three successful synthetic fixture invocations"
```

Allowed lifecycle transitions are enforced by the CLI:

- `pending -> active`
- `pending -> failed`
- `active -> quarantined`
- `quarantined -> repaired_active`
- `quarantined -> failed`
- `repaired_active -> quarantined`
- `* -> deprecated`

Forbidden transitions fail fast, including `active -> pending`, `deprecated -> *`, and `failed -> active`.

# Step 5 — Append To State Log

State changes are appended automatically to:

```text
vault/config/artifact-producer-state-log.md
```

Do not edit the state log by hand during the default flow. The append-only log is lifecycle evidence for later audits and repair work.

# Step 6 — Verify Registry Resolution

Confirm the producer resolves for each artifact type and medium it claims:

```bash
python3 scripts/artifact_registry.py get --producer-id PRODUCER_ID
python3 scripts/artifact_registry.py resolve --artifact-type ARTIFACT_TYPE --medium MEDIUM
python3 scripts/check_artifact_producer_concurrency.py
```

Expected results:

- `get` returns the registered producer.
- `resolve` returns that producer once it is `active` or `repaired_active`.
- The concurrency check reports no stale locks, duplicate registrations, or orphaned locks.

# Source Type Handling

## existing_mcp

Use `mcp_path`. The path must point to a local wrapper that can be launched for a synthetic fixture. The health checker will execute:

- The file directly when executable.
- `python3 {mcp_path}` for `.py`.
- `node {mcp_path}` for `.js`, `.mjs`, or `.cjs`.

The fixture path, artifact type, and medium are passed as CLI arguments and environment variables.

## cli_tool

Use `cli_command`. The command is split with shell-style quoting and receives the fixture path as an argument unless `{fixture}` is already present.

Supported placeholders:

- `{fixture}`
- `{artifact_type}`
- `{medium}`
- `{producer_id}`

## api_wrapper

Use `api_endpoint`. The health checker sends an HTTP `POST` with JSON fixture data, `artifact_type`, `medium`, `producer_id`, and `synthetic_fixture: true`.

If `api_key_env_var` is set and present in the environment, it is sent as a bearer token.

## new_mcp_via_source_capability

Do not build inline in this skill. Create or use the existing capability flow:

1. Run `source-capability` to identify the producer wrapper source.
2. Run `build-mcp-server` or `register-mcp` as appropriate.
3. Create a synthetic fixture.
4. Return to this skill and register the finished wrapper as `pending`.

# Outputs

Produce a concise registration summary:

```yaml
producer_id: PRODUCER_ID
registry_status: registered|no_op|conflict|failed
fixture_status: pass|fail|not_run
state: pending|active|failed
state_log_updated: true|false
registry_path: vault/config/artifact-producers.md
health_report_path: /tmp/producer-health.json
concurrency_report: pass|fail
```

If any step fails, include the exact command result and the file path that needs attention. Do not request confirmation; stop with the actionable failure.
