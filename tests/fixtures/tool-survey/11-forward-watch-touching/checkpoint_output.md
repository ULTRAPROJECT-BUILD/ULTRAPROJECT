```yaml
checkpoint:
  ticket_id: T-053
  Tier selected: T3
  Decision: ACCEPT
  Reasoning: The artifact clears the bar; downstream post-FX will modify the rendered bytes.
  forward_watch:
    - type: artifact_touching
      operation: post-FX wrap
      target_phase_or_ticket: T-060
      expected_artifact_change: Apply depth of field, grain, ACES tone-map, bloom, and vignette to the rendered shot.
```
