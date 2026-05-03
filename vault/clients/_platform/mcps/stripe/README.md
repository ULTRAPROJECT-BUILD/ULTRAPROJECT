# Stripe MCP Server

Restricted Stripe API access for the AI agent platform. This MCP server provides a minimal, policy-enforced interface to Stripe for payment collection only.

## Capabilities

| Allowed | Blocked |
|---------|---------|
| Create payment links | Issue refunds |
| Read payment status | Transfer money |
| List payments | Modify account settings |
| | Access/store payment methods |

## Tools

### `create_payment_link`
Creates a Stripe payment link and returns the URL.

**Parameters:**
- `amount_cents` (int, required) — Amount in cents (e.g. 1000 = $10.00)
- `currency` (str, default: "usd") — ISO currency code
- `description` (str) — Human-readable description
- `customer_email` (str) — Customer email for receipt
- `metadata` (dict) — Arbitrary key-value metadata

### `check_payment_status`
Checks the status of a PaymentIntent.

**Parameters:**
- `payment_intent_id` (str, required) — Stripe PaymentIntent ID (starts with `pi_`)

### `list_payments`
Lists recent payments, optionally filtered by customer email.

**Parameters:**
- `limit` (int, default: 10) — Number of results (1-100)
- `customer_email` (str) — Filter by customer email

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `STRIPE_RESTRICTED_KEY` | Yes | Stripe restricted API key with **only** `payment_links:write`, `payment_intents:read`, `charges:read` permissions |

## Setup

1. In the Stripe Dashboard, create a **Restricted Key** with only these permissions:
   - Payment Links: Write
   - Payment Intents: Read
   - Charges: Read

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set the environment variable:
   ```bash
   export STRIPE_RESTRICTED_KEY="rk_live_..."
   ```

4. Run the server:
   ```bash
   python3 server.py
   ```

## Security Notes

- The restricted key is enforced at both the Stripe API level and within this server's code.
- Blocked operations (refunds, transfers, payouts, etc.) are rejected before reaching Stripe.
- `list_payments(customer_email=...)` filters by the email recorded on the payment intent metadata, receipt email, or expanded charge billing details. It does not require a Stripe Customer object.
- Never commit API keys. Always use environment variables.
