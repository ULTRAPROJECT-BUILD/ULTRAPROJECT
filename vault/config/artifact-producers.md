---
type: artifact-producers-registry
version: 1
last_updated: 2026-05-10T15:53
schema_version: 1
---

# Artifact Producers Registry

This is the central registry of artifact producers (image-gen, 3D, video, audio, etc.) that can satisfy artifact requests from Visual Specifications.

Each producer is operator-registered manually OR via the existing source-capability flow. V7-A does NOT auto-bootstrap producers; that's V7-B (deferred).

## Producers

(none registered — operator registers as needed)

```yaml
producers: []
```

## Adding a producer

Use the `register-artifact-producer` skill. The skill handles concurrent registration safety, schema validation, lifecycle state assignment, and synthetic fixture testing before promoting from `pending` to `active`.

## Lifecycle states

- `pending`: just registered; needs ≥3 successful synthetic-fixture invocations to promote to `active`
- `active`: in production use; rolling success rate ≥80% and last fixture <14 days old
- `repaired_active`: previously quarantined; operator confirmed repair; back to active
- `quarantined`: 2 consecutive failures or success rate <50%; fallback chain takes over; repair ticket created
- `failed`: terminal failure; superseded by replacement
- `deprecated`: replaced by newer producer (`canonical_replaces` field on successor points back)
