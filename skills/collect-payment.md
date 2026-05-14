---
type: skill
name: collect-payment
description: Generates payment links/addresses, checks payment status, records operator-mediated reminders, gates work behind payment
inputs:
  - client_slug (required — client to collect payment from)
  - amount_usd (required — amount to charge)
  - description (required — what the payment is for, e.g. "Onboarding setup fee")
  - "payment_type (optional — 'onboarding', 'monthly', or 'custom'; default: 'custom')"
---

# Collect Payment

You are collecting payment from a client. This skill generates payment links, checks status, and gates work behind payment confirmation.

## Process

### Step 1: Read Configuration

1. Read [[platform]] for payment config:
   - `pricing.payment_methods` — Stripe is the rail shipped by default (see "Other rails" at the bottom of this skill)
   - `pricing.stripe_restricted_key` — Stripe API key (create-links + read only)
   - `pricing.payment_reminder_days` — when to send reminders
   - `pricing.auto_churn_days` — when to auto-churn unpaid clients

2. Read `vault/clients/{client_slug}/config.md` for client details.

### Step 2: Generate Payment Options

Use the Stripe MCP to create a payment link:

1. Amount: `{amount_usd}` USD
2. Description: `{description}`
3. Customer contact from client config
4. Metadata: `client_slug`, `payment_type`, `customer_contact`
5. Capture the payment link URL and returned Stripe payment link ID.

### Step 3: Prepare Payment Request

Draft this payment request for operator-mediated sending:

```
Subject: Payment Required — {description}

Hi {name},

{For onboarding: "Your agent setup is ready. To proceed, please complete payment:"}
{For monthly: "Your monthly service fee is due:"}
{For custom: "Payment is required for: {description}"}

**Amount: ${amount_usd} USD**

Pay by credit card (Stripe):
{stripe_payment_link}

Payment is required before work can begin/continue.
```

### Step 4: Update Client Config

1. Update `vault/clients/{client_slug}/config.md`:
   ```yaml
   payment_status: pending
   payment_amount_usd: {amount_usd}
   payment_requested_date: {now}
   payment_type: {payment_type}
   ```
2. Append a work log note or payment reminder note with:
   - Stripe payment link ID
   - Stripe payment URL
   - Requested amount and date

### Step 5: Create Reminder Schedule

1. Create a ticket in the client's namespace:
   - Title: "Payment follow-up: {description}"
   - Status: `waiting`
   - Priority: `medium`
   - Body: "Check payment status. Match against the stored payment link ID, requested amount, customer contact, and metadata. Prepare reminders per schedule. Auto-churn if no payment after {auto_churn_days} days."
   - Tags: [payment, reminder]

2. The orchestrator or operator-run chat cycle will check this ticket periodically.

### Step 6: Check Payment Status (called on subsequent runs)

**Stripe:**
1. Use the Stripe MCP's `list_payments` tool with the configured customer filter to find recent payments from this client. Match against the stored payment link ID, amount, description, and metadata captured when the request was prepared.
2. If a specific `payment_intent_id` is known from a receipt or prior result, use `check_payment_status` instead.
3. If paid: update client config `payment_status: paid`, close the payment ticket.

**Manual confirmation:**
- If the client reports "paid" or forwards a receipt through the operator, match it to the payment ticket.
- Update payment status accordingly.

### Step 7: Send Reminders

Based on `payment_reminder_days` config:
1. **Day 2:** "Friendly reminder — your payment of ${amount_usd} is pending."
2. **Day 7:** "Your payment is overdue. Work is paused until payment is received."

### Step 8: Auto-Churn

After `auto_churn_days` (default 14) with no payment:
1. Update client status to `churned` in config and registry.
2. Pause all client projects.
3. Draft final notice: "Your account has been deactivated due to non-payment. Contact us to reactivate."
4. Run [[delete-client-data]] after 30 days (data retention period).

## Payment Gate

The orchestrator checks `payment_status` in client config before spawning agents for client work:
- `paid` or `active` → proceed with work
- `pending` → only allow clarification, scoping, and payment collection. Do not build capabilities, run integrations, or execute client task work.
- `overdue` → pause all work, prepare reminder
- `churned` → no work, account inactive

## Output

Return:
- **Payment link:** Stripe URL
- **Payment request drafted:** true/false
- **Client config updated:** true
- **Reminder ticket created:** ticket ID

## Known Gaps (Fix Before Production Payments)

These issues were identified during scope-detection testing and must be resolved before `pricing.require_payment` is set to `true`:

1. **Client-wide payment blocking:** Setting `payment_status: pending` blocks ALL client work, not just the scope expansion that triggered the invoice. Need project-scoped or ticket-scoped billing so a change order for Project B does not freeze Project A.
2. **Ticket-referenced feedback bypasses scope detection:** A client saying "re T-015, also add X" must still hit scope-change detection. The ticket-reference route needs scope-expansion checking too.
3. **Scope matrix vs original request conflict:** A client can mention something originally but have it scoped OUT in the creative brief. Current logic would misclassify that as a free fix. Scope detection must check the scope matrix (creative brief), not just the original request.
4. **Unreliable revision counter:** The `enrichment` tag is used on workstream tickets too, causing overcounting of revision cycles. Need a dedicated `client-revision` tag or a counter field on the project.
5. **Feedback routing incomplete:** The feedback path must classify scope before appending or ticketizing requested changes.

(Learned from 2026-03-18-scope-payment-integration-gaps, 2026-03-18)

## Other Rails

This skill ships with Stripe as the only payment rail. If you want to add another rail (crypto wallet, ACH, invoicing, etc.), the pattern is:

1. Build or source an MCP that talks to your provider — see [[build-mcp-server]] and [[source-capability]].
2. Register it in `.mcp.json` (or `.mcp.template.json` for the version-controlled template).
3. Extend Step 2 ("Generate Payment Options") and Step 6 ("Check Payment Status") in this skill to call your new MCP alongside Stripe.

The system is designed to be self-extending. The wallet MCP that previously shipped here was removed for the OSS distribution because handling crypto receipts safely is downstream-specific.

## Security Notes

- The Stripe MCP uses a RESTRICTED API key — it can only create payment links and read status. It CANNOT issue refunds, transfer funds, or modify the Stripe account.
- Payment requests are logged in the client config and payment follow-up ticket for audit.

## See Also

- [[platform]]
- [[delete-client-data]]
- [[orchestrator]]
