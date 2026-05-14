tool_fit_rigor_tier: default
tool_survey_snapshot: expected_snapshot_output.md

## Load-Bearing Capabilities
| Capability | Bar |
|---|---|
| `fixture_capability` | Fixture bar. |

## Architecture Decisions
| ID | Decision | Binding |
|---|---|---|
| AD-001 | First execution stack | tool_slug: fixture-tool; tool_stack_refs: [fixture:current@1] |
| AD-002 | Second execution stack | tool_slug: fixture-other; tool_stack_refs: [fixture:other@1] |
