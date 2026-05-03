---
type: config
title: "Token Usage & Metering"
description: "Tracks per-agent invocation counts, token usage, estimated spend, and relative monthly credit pool usage. Written by chat-native orchestration cycles and scripts/agent_runtime.py."
updated: ""
---

# Token Usage & Metering

## Agent Credit Pools

Usage is tracked as relative invocation units month-to-date until provider-specific credit APIs are available.

| Agent | Enabled | Used (month) | Budget (month) | Pct Used | Status |
|-------|---------|--------------|----------------|----------|--------|
| claude | true | 0 | 10000 | 0% | healthy |
| codex | true | 0 | 10000 | 0% | healthy |
| gemini | false | 0 | 10000 | 0% | disabled |

## Daily Usage

| Date | Agent | Client | Project | Task Type | Invocations | Tokens In | Tokens Out | Est Cost |
|------|-------|--------|---------|-----------|-------------|-----------|------------|----------|

## Rolling Totals

| Window | Claude Invocations | Codex Invocations | Gemini Invocations | Total Tokens | Est Cost |
| ------ | ------------------ | ----------------- | ------------------ | ------------ | -------- |
| last_hour | 0 | 0 | 0 | 0 | $0.0000 |
| last_24h | 0 | 0 | 0 | 0 | $0.0000 |
| last_7d | 0 | 0 | 0 | 0 | $0.0000 |

## Per-Client Summary

| Client | Claude Invocations | Codex Invocations | Gemini Invocations | Total Tokens | Est Cost |
| ------ | ------------------ | ----------------- | ------------------ | ------------ | -------- |

## See Also

- [[platform]]
- [[orchestrator]]
