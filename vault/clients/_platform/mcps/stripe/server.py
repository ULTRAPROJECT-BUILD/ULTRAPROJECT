"""
Stripe MCP Server — Restricted Payment Operations

Provides RESTRICTED Stripe API access for a self-bootstrapping AI agent.
The restricted key can ONLY: create payment links, read payment status, list payments.
It CANNOT: issue refunds, transfer money, modify account settings, access payment methods.
"""

import json
import os
from typing import Optional

import stripe
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

STRIPE_RESTRICTED_KEY = os.environ.get("STRIPE_RESTRICTED_KEY", "")
if STRIPE_RESTRICTED_KEY:
    stripe.api_key = STRIPE_RESTRICTED_KEY

_NOT_CONFIGURED_MSG = (
    "Stripe MCP is not configured. Set STRIPE_RESTRICTED_KEY environment variable. "
    "Generate a restricted key in the Stripe dashboard with ONLY: "
    "payment_links (write), payment_intents (read), charges (read)."
)

def _require_key():
    if not STRIPE_RESTRICTED_KEY:
        return _NOT_CONFIGURED_MSG
    return None


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _intent_email_candidates(intent) -> set[str]:
    emails: set[str] = set()

    receipt_email = intent.get("receipt_email")
    if receipt_email:
        emails.add(_normalize_email(receipt_email))

    metadata = dict(intent.metadata) if intent.metadata else {}
    for key in ("customer_email", "email"):
        candidate = metadata.get(key)
        if candidate:
            emails.add(_normalize_email(candidate))

    latest_charge = intent.get("latest_charge")
    if latest_charge and not isinstance(latest_charge, str):
        billing_details = latest_charge.get("billing_details") or {}
        charge_email = billing_details.get("email") or latest_charge.get("receipt_email")
        if charge_email:
            emails.add(_normalize_email(charge_email))

    return emails

# ---------------------------------------------------------------------------
# Blocked operations — safety guardrails
# ---------------------------------------------------------------------------

_BLOCKED_OPERATIONS = frozenset(
    [
        "refund",
        "transfer",
        "payout",
        "account_update",
        "payment_method",
        "bank_account",
        "card_delete",
        "subscription_cancel",
    ]
)


def _assert_not_blocked(operation: str) -> None:
    """Raise if the caller attempts a blocked operation."""
    for blocked in _BLOCKED_OPERATIONS:
        if blocked in operation.lower():
            raise PermissionError(
                f"Operation '{operation}' is blocked by policy. "
                "This restricted key can only create payment links, "
                "read payment status, and list payments."
            )


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Stripe Payments",
    description=(
        "Restricted Stripe API access for the AI agent platform. "
        "Can create payment links, check payment status, and list payments. "
        "Cannot issue refunds, transfer money, or modify account settings."
    ),
)


@mcp.tool()
def create_payment_link(
    amount_cents: int,
    currency: str = "usd",
    description: str = "",
    customer_email: str = "",
    metadata: Optional[dict] = None,
) -> str:
    """Create a Stripe payment link.

    Args:
        amount_cents: Amount in cents (e.g. 1000 = $10.00).
        currency: Three-letter ISO currency code (default: usd).
        description: Human-readable description of the payment.
        customer_email: Optional customer email for receipt.
        metadata: Optional dict of key-value metadata pairs.

    Returns:
        The payment link URL, or an error message.
    """
    err = _require_key()
    if err:
        return err
    _assert_not_blocked("create_payment_link")

    if amount_cents <= 0:
        return "Error: amount_cents must be a positive integer."
    if amount_cents > 99_999_999:  # Stripe max ~$999,999.99
        return "Error: amount_cents exceeds the maximum allowed value."

    try:
        # Create a one-time price for the payment link
        price = stripe.Price.create(
            unit_amount=amount_cents,
            currency=currency.lower(),
            product_data={"name": description or "Payment"},
        )

        link_params: dict = {
            "line_items": [{"price": price.id, "quantity": 1}],
        }

        if metadata:
            link_params["metadata"] = metadata

        if customer_email:
            link_params["metadata"] = link_params.get("metadata", {})
            link_params["metadata"]["customer_email"] = customer_email

        payment_link = stripe.PaymentLink.create(**link_params)

        result = {
            "url": payment_link.url,
            "id": payment_link.id,
            "amount": f"{amount_cents / 100:.2f} {currency.upper()}",
            "description": description,
            "metadata": link_params.get("metadata", {}),
        }
        if customer_email:
            result["customer_email"] = customer_email

        return json.dumps(result, indent=2)

    except stripe.error.PermissionError as e:
        return f"Error: Stripe permission denied — {e.user_message}"
    except stripe.error.InvalidRequestError as e:
        return f"Error: Invalid request — {e.user_message}"
    except stripe.error.StripeError as e:
        return f"Error: Stripe API error — {e.user_message}"
    except Exception as e:
        return f"Error: Unexpected failure — {e}"


@mcp.tool()
def check_payment_status(payment_intent_id: str) -> str:
    """Check the status of a payment by its PaymentIntent ID.

    Args:
        payment_intent_id: The Stripe PaymentIntent ID (starts with pi_).

    Returns:
        Payment status and details, or an error message.
    """
    err = _require_key()
    if err:
        return err
    _assert_not_blocked("check_payment_status")

    if not payment_intent_id or not payment_intent_id.startswith("pi_"):
        return "Error: Invalid PaymentIntent ID. Must start with 'pi_'."

    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        result = {
            "id": intent.id,
            "status": intent.status,
            "amount": f"{intent.amount / 100:.2f} {intent.currency.upper()}",
            "currency": intent.currency,
            "created": intent.created,
            "description": intent.description or "",
            "customer": intent.customer or "",
            "metadata": dict(intent.metadata) if intent.metadata else {},
        }

        # Add human-readable status
        status_labels = {
            "succeeded": "Payment successful",
            "processing": "Payment is processing",
            "requires_payment_method": "Awaiting payment method",
            "requires_confirmation": "Awaiting confirmation",
            "requires_action": "Awaiting customer action (e.g. 3D Secure)",
            "canceled": "Payment was canceled",
            "requires_capture": "Authorized, awaiting capture",
        }
        result["status_label"] = status_labels.get(intent.status, intent.status)

        return json.dumps(result, indent=2)

    except stripe.error.PermissionError as e:
        return f"Error: Stripe permission denied — {e.user_message}"
    except stripe.error.InvalidRequestError as e:
        return f"Error: Invalid request — {e.user_message}"
    except stripe.error.StripeError as e:
        return f"Error: Stripe API error — {e.user_message}"
    except Exception as e:
        return f"Error: Unexpected failure — {e}"


@mcp.tool()
def list_payments(limit: int = 10, customer_email: str = "") -> str:
    """List recent payments, optionally filtered by customer email.

    Args:
        limit: Maximum number of payments to return (1-100, default 10).
        customer_email: Optional email to filter payments by.

    Returns:
        Formatted list of recent payments, or an error message.
    """
    err = _require_key()
    if err:
        return err
    _assert_not_blocked("list_payments")

    limit = max(1, min(limit, 100))

    try:
        params: dict = {"limit": max(limit, 100) if customer_email else limit}
        if customer_email:
            params["expand"] = ["data.latest_charge"]
            customer_email = _normalize_email(customer_email)

        intents = stripe.PaymentIntent.list(**params)

        if not intents.data:
            return "No payments found."

        payments = []
        for intent in intents.data:
            email_candidates = _intent_email_candidates(intent)
            if customer_email and customer_email not in email_candidates:
                continue

            payments.append(
                {
                    "id": intent.id,
                    "status": intent.status,
                    "amount": f"{intent.amount / 100:.2f} {intent.currency.upper()}",
                    "description": intent.description or "",
                    "created": intent.created,
                    "receipt_email": intent.get("receipt_email") or "",
                    "customer_email_matches": sorted(email_candidates),
                    "metadata": dict(intent.metadata) if intent.metadata else {},
                }
            )
            if len(payments) >= limit:
                break

        if not payments:
            return "No payments found."

        result = {
            "total_returned": len(payments),
            "payments": payments,
        }
        return json.dumps(result, indent=2)

    except stripe.error.PermissionError as e:
        return f"Error: Stripe permission denied — {e.user_message}"
    except stripe.error.InvalidRequestError as e:
        return f"Error: Invalid request — {e.user_message}"
    except stripe.error.StripeError as e:
        return f"Error: Stripe API error — {e.user_message}"
    except Exception as e:
        return f"Error: Unexpected failure — {e}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
