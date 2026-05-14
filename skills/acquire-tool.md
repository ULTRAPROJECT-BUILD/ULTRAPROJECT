---
type: skill
name: acquire-tool
description: Dry-run-first tool acquisition with operator-approved manifests, spending reservations, rollback, functional canaries, and register-mcp proposals
inputs:
  - tool_slug (required)
  - project (required)
  - client (optional; default personal)
  - authorization (required when spend is involved; decision_authorization block from OAI-PLAN/OAI-TOOL/OAI-SPEND)
  - mode (optional; manifest | validate | execute | rollback; default manifest)
  - execute (optional; default false; real mutation requires true)
---

# Acquire Tool

Acquire-Tool is the only Stage 3 path for installing or activating a catalog tool. It is safety-first and dry-run-first. It prepares transaction manifests, reserves/captures spend only inside an operator authorization envelope, runs a functional canary, and writes MCP registration proposals for [[register-mcp]]. It never directly edits `.mcp.json`.

## Load-Bearing Rules

1. **Dry-run is the default.** Running `scripts/acquire_tool.py execute <manifest>` without `--execute` validates and prints the manifest flow only. Real mutation requires `--execute`.
2. **Operator approval is mandatory.** Execute refuses any manifest unless `operator_approval_status: approved` and `operator_approval_signature` are present. If the operator declines, release any reservation and stop.
3. **Project-local install by default.** Use a project-local Python venv, npm prefix, or `vault/clients/_platform/tools-cache/` for cached binaries. Global installs require explicit approval in the manifest.
4. **Binary downloads are pinned.** Manifest must include version, HTTPS source URL, sha256, and TLS provenance check. Checksum mismatch blocks install and triggers rollback.
5. **No secrets in vault or OAI bodies.** Accept env var names or keychain/operator-action prompts only. Execute reads secrets from env/keychain at the moment of use and does not write them back.
6. **MCP registration goes through register-mcp.** Acquire-Tool may write `vault/clients/_platform/mcps/{tool-slug}/registration-proposal.yaml`; it must not edit `.mcp.json`.
7. **Spending capture requires reservation.** Capture must trace to reservation_id, quote_id, authorization_id, and `max_authorized_amount_usd`.
8. **Rollback is best-effort and scoped.** Uninstall or remove only what this transaction installed; release unused reservations; record zero actual spend when no capture happened.

## Process

### 1. Read Catalog + Authorization

Read the selected Tool Discovery catalog entry and the resolved OAI `decision_authorization` block. Reject immediately if the OAI body or manifest contains literal secret values. Env var names such as `OPENAI_API_KEY` are allowed; actual values are not.

### 2. Produce Manifest

Run:

```bash
python3 scripts/acquire_tool.py manifest \
  --tool-slug "{tool_slug}" \
  --project-slug "{project}" \
  --client-slug "{client}" \
  --authorization "{authorization_json_or_path}" \
  --out "{snapshot_dir}/tool-acquisition/{tool_slug}-manifest.json"
```

The manifest must include planned steps, files to touch, spend reservation mode, rollback plan, operator approval status, and any MCP registration proposal path.

### 3. Validate + Dry-Run

Run:

```bash
python3 scripts/acquire_tool.py validate "{manifest_path}"
python3 scripts/acquire_tool.py execute "{manifest_path}" --catalog-entry "{catalog_entry_path}" --json
```

This validates schema, secrets policy, local/global install policy, binary provenance, OS support, and `.mcp.json` isolation. It performs no install, no capture, no registry mutation.

### 4. Operator Approval

Surface the manifest to the operator. Do not execute until the operator approves the exact manifest. Record:

```yaml
operator_approval_status: approved
operator_approval_signature:
  operator_id: <operator>
  signed_at: <machine-local timestamp>
  approval_source: <project log / OAI pointer>
```

If declined, release any existing reservation and stop.

### 5. Spending Reservation

If `paid_via: spending_mcp` and the spending MCP is registered in `.mcp.json`, execute runs:

```text
quote_spend -> reserve_spend -> install -> canary -> capture_spend
```

If quote/reserve exceeds caps, do not install. Raise OAI-SPEND-NNN using [[orchestrator]] routing. If the spending MCP is not registered, switch to `operator_out_of_band`: the operator acquires manually and Acquire-Tool only canary-verifies presence.

### 6. Install + Canary

Install only through structured adapters: project-local venv, project-local npm prefix, or OneShot tools cache. Then run:

```bash
python3 scripts/check_tool_acquisition.py \
  --catalog-entry "{catalog_entry_path}" \
  --install-root "{install_root}" \
  --evidence-dir "{transaction_dir}" \
  --json
```

The canary must exercise actual capability via `acquisition.canary_steps`, not just `--version`.

### 7. Capture + Registration Proposal

After canary pass, capture spend against the reservation. If the tool exposes an MCP, write:

```text
vault/clients/_platform/mcps/{tool-slug}/registration-proposal.yaml
```

Then stop and route actual registration through [[register-mcp]], including its security review, admin approval, and admin-authored `.mcp.json` edit.

## Failure Paths

- Manifest validation failure: stop; no reservation, install, capture, or proposal.
- Spending cap exceeded: raise OAI-SPEND-NNN; no install.
- Operator decline: release reservation; no install; no proposal.
- Install/checksum/canary failure: rollback scoped install changes, release reservation, record actual spend zero if capture did not happen.
- Capture failure: rollback install changes and surface the capture failure for operator review.
- Out-of-band path: if the canary cannot verify presence, leave `tool_presence_canary` waiting and keep dependent tickets blocked.

## Commands

```bash
python3 scripts/acquire_tool.py --help
python3 scripts/check_tool_acquisition.py --help
```

## See Also

- [[orchestrator]]
- [[project-plan]]
- [[register-mcp]]
- [[source-capability]]
