---
type: skill
name: delete-client-data
description: Deletes a client's entire directory on request, churn, or engagement end — GDPR/CCPA-aligned
inputs:
  - client_slug (required — the client to delete)
  - reason (required — "client_request", "churn", "engagement_end", "admin_order")
  - prepare_confirmation (optional — default true; draft confirmation for operator-mediated sending)
---

# Delete Client Data

You are deleting all data for a specific client. This is triggered by client request, churn, engagement end, or admin order.

## Process

### Step 1: Validate

1. Read `vault/clients/_registry.md` to confirm the client exists.
2. Read `vault/clients/{client_slug}/config.md` to get client details.
3. If the client doesn't exist: return error "Client not found."

### Step 2: Pre-Deletion Inventory

1. List all files and directories under `vault/clients/{client_slug}/`.
2. Count: projects, tickets, MCPs, skills, snapshots, decisions, lessons.
3. Record this inventory — it will be logged.

### Step 3: Admin Approval (MANDATORY — blocks deletion regardless of reason)

**All data deletions require admin approval.** No exceptions, regardless of `reason`.

1. Write an admin approval request in the relevant ticket/project log and surface it in chat with:
   - Subject: "🔒 Approval needed: delete client data — {client_slug}"
   - Body: client name, reason for deletion, pre-deletion inventory (from Step 2), and whether active work exists.
2. Create a ticket with `status: waiting`, `assignee: human`, `priority: high`:
   - Title: "Approve data deletion: {client_slug} (reason: {reason})"
   - Description: include all request details plus the inventory.
3. **STOP and wait.** Do NOT proceed to Step 4 until the admin approves the ticket (status changed to `closed` by admin or manual update).
4. If admin denies: do NOT delete. Close the ticket with "Denied by admin." Stop here.

**Why:** Data deletion is irreversible. Even for client requests, admin should verify the request is legitimate (not a social engineering attack) before data is destroyed.

### Step 3b: Check for Active Work and MCPs

1. Check for any tickets with status `in-progress`. If found, note in admin notification.
2. Check for any registered MCPs in `.mcp.json` that point to this client's directory.
   - If found: remove them from `.mcp.json` before deleting files.

### Step 4: Delete Client Directory

1. Delete the entire `vault/clients/{client_slug}/` directory and all contents.
2. This removes: config, projects, tickets, decisions, lessons, MCPs, skills, snapshots — everything.

### Step 5: Update Registry

1. Read `vault/clients/_registry.md`.
2. Either remove the client's row or update their status to `deleted`.
3. Write back the updated registry.

### Step 6: What is NOT Deleted

The following are explicitly preserved (covered by ToS de-identification consent):
- **De-identified playbooks** in `vault/archive/playbooks/` — these contain no client PII.
- **De-identified patterns** in `vault/archive/patterns/` — aggregate insights, no PII.
- **Sanitized MCPs** in `vault/archive/mcps/` — code with credentials stripped.
- **Sanitized skills** in `vault/archive/skills/` — generic instruction templates.

These are de-identified by design and cannot be traced back to the client.

### Step 7: Prepare Confirmation

If `prepare_confirmation` is true:
1. Draft a confirmation for operator-mediated sending:
   ```
   Subject: Your data has been deleted

   Hi {name},

   As requested, all your data has been permanently deleted from our systems.
   This includes all projects, tasks, configurations, and communications.

   De-identified, anonymized insights (which contain no personal or business-identifying
   information) are retained per our Terms of Service.

   If you have any questions, please contact the operator.
   ```
2. Record where the confirmation draft was saved.

### Step 8: Log the Deletion

1. Append to `vault/config/admin-log.md`:
   ```
   - {now}: CLIENT DELETED — slug: {client_slug}, reason: {reason},
     files_deleted: {count}, projects: {count}, tickets: {count}
   ```

## Output

Return:
- **Client deleted:** {slug}
- **Reason:** {reason}
- **Files removed:** {count}
- **MCPs deregistered:** {list or "none"}
- **Confirmation drafted:** true/false
- **Admin log updated:** true

## Safety

- This operation is IRREVERSIBLE. There is no "undo."
- **All deletions require admin approval (Step 3).** No exceptions, regardless of reason.
- The pre-deletion inventory is logged to admin-log before deletion occurs.
- Active in-progress work is flagged in the admin approval request.
- De-identified archive content is preserved by design — this is disclosed in the ToS.

## See Also

- [[archive-capability]]
- [[archive-project]]
- [[orchestrator]]
