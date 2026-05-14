tool_fit_rigor_tier: default
tool_survey_snapshot: expected_snapshot_output.md

## Load-Bearing Capabilities
| Capability | Bar |
|---|---|
| `fixture_capability` | Fixture bar. |

## Architecture Decisions
| ID | Decision | Binding |
|---|---|---|
| AD-001 | Current execution stack | tool_slug: fixture-tool; tool_stack_refs: [fixture:current@1] |
| AD-002 | Tool replan selection | tool_slug: fixture-alt; tool_stack_refs: [fixture:alt@1] |
