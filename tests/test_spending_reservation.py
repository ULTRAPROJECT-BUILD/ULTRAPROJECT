from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = REPO_ROOT / "vault" / "clients" / "_platform" / "mcps" / "spending" / "server.py"
SCHEMA_PATH = REPO_ROOT / "schemas" / "spending-reservation.schema.json"


def load_module(tmp_path, monkeypatch, *, daily="1000", monthly="5000"):
    monkeypatch.setenv("SPENDING_LOG_PATH", str(tmp_path / "spending-log.md"))
    monkeypatch.setenv("SPENDING_RESERVATION_LOG_PATH", str(tmp_path / "spending-reservations.json"))
    monkeypatch.setenv("DAILY_CAP_USD", daily)
    monkeypatch.setenv("MONTHLY_CAP_USD", monthly)
    spec = importlib.util.spec_from_file_location(f"spending_under_test_{id(tmp_path)}", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def run(coro):
    return json.loads(asyncio.run(coro))


def test_quote_reserve_capture_release_state_machine_and_idempotency(tmp_path, monkeypatch):
    mod = load_module(tmp_path, monkeypatch)

    quote = run(
        mod.quote_spend(
            project_slug="render-fixture-007",
            vendor="SideFX",
            amount_usd=269,
            recurrence="annual",
            category="tool_acquisition",
            requested_by_tool_stack="vendor:sidefx/houdini-indie@latest",
        )
    )
    assert quote["status"] == "OK"

    reserve = run(
        mod.reserve_spend(
            quote_id=quote["quote_id"],
            authorization_id="auth-houdini-001",
            expires_at="2099-01-01T00:00:00+00:00",
            project_slug="render-fixture-007",
            category="tool_acquisition",
            max_authorized_amount_usd=269,
        )
    )
    assert reserve["status"] == "OK"
    reservation = reserve["reservation"]
    assert reservation["state"] == "reserved"
    assert reservation["authorization_id"] == "auth-houdini-001"

    capture = run(
        mod.capture_spend(
            reservation_id=reservation["reservation_id"],
            actual_amount_usd=269,
            receipt_ref="vault/clients/example/snapshots/render-fixture-007/receipt.json",
            project_slug="render-fixture-007",
            category="tool_acquisition",
        )
    )
    assert capture["status"] == "OK"
    assert capture["capture"]["state"] == "captured"
    assert capture["capture"]["actual_amount_usd"] == 269

    again = run(
        mod.capture_spend(
            reservation_id=reservation["reservation_id"],
            actual_amount_usd=269,
            receipt_ref="vault/clients/example/snapshots/render-fixture-007/receipt.json",
            project_slug="render-fixture-007",
            category="tool_acquisition",
        )
    )
    assert again["status"] == "OK"
    assert again["idempotent"] is True
    assert again["capture"]["capture_id"] == capture["capture"]["capture_id"]

    release = run(mod.release_reservation(reservation["reservation_id"], "too late"))
    assert release["status"] == "REJECTED"
    assert release["reason"] == "reservation_already_captured"

    budget = run(mod.check_spending_budget())
    assert budget["daily_spent_usd"] == 269
    assert budget["active_reserved_usd"] == 0


def test_cap_enforcement_counts_active_reservations(tmp_path, monkeypatch):
    mod = load_module(tmp_path, monkeypatch, daily="15", monthly="100")

    first = run(mod.quote_spend("demo", "Vendor", 10, "one_time", "tool_usage", "stack@1"))
    assert first["status"] == "OK"
    reserve = run(
        mod.reserve_spend(
            first["quote_id"],
            "auth-001",
            "2099-01-01T00:00:00+00:00",
            project_slug="demo",
            category="tool_usage",
            max_authorized_amount_usd=10,
        )
    )
    assert reserve["status"] == "OK"

    second = run(mod.quote_spend("demo", "Vendor", 6, "one_time", "tool_usage", "stack@1"))
    assert second["status"] == "REJECTED"
    assert second["reason"] == "daily_cap_exceeded"
    assert second["projected_balance_usd"] < 0


def test_release_sets_actual_zero_and_capture_is_blocked(tmp_path, monkeypatch):
    mod = load_module(tmp_path, monkeypatch)

    quote = run(mod.quote_spend("demo", "Vendor", 12, "one_time", "other", "stack@1"))
    reserve = run(
        mod.reserve_spend(
            quote["quote_id"],
            "auth-release-001",
            "2099-01-01T00:00:00+00:00",
            project_slug="demo",
            category="other",
            max_authorized_amount_usd=12,
        )
    )
    reservation_id = reserve["reservation"]["reservation_id"]
    release = run(mod.release_reservation(reservation_id, "operator abort", project_slug="demo", category="other"))
    assert release["status"] == "OK"
    assert release["release"]["state"] == "released"
    assert release["release"]["actual_amount_usd"] == 0

    capture = run(mod.capture_spend(reservation_id, 12, "vault/receipt.json", project_slug="demo", category="other"))
    assert capture["status"] == "REJECTED"
    assert capture["reason"] == "reservation_is_released"


def test_expired_reservations_auto_release(tmp_path, monkeypatch):
    mod = load_module(tmp_path, monkeypatch)

    quote = run(mod.quote_spend("demo", "Vendor", 7, "one_time", "api_call", "stack@1"))
    reserve = run(
        mod.reserve_spend(
            quote["quote_id"],
            "auth-expire-001",
            "2000-01-01T00:00:00+00:00",
            project_slug="demo",
            category="api_call",
            max_authorized_amount_usd=7,
        )
    )
    reservation_id = reserve["reservation"]["reservation_id"]

    # Any subsequent operation performs the expiry sweep.
    budget = run(mod.check_spending_budget())
    assert budget["active_reserved_usd"] == 0
    capture = run(mod.capture_spend(reservation_id, 7, "vault/receipt.json", project_slug="demo", category="api_call"))
    assert capture["status"] == "REJECTED"
    assert capture["reason"] == "reservation_is_expired"


def test_existing_record_expenditure_api_still_works(tmp_path, monkeypatch):
    mod = load_module(tmp_path, monkeypatch)

    recorded = run(mod.record_expenditure(2.5, "fixture API call", "OpenAI", "api"))
    assert recorded["status"] == "approved"
    log = run(mod.get_spending_log(1))
    assert log["total_approved_usd"] == 2.5
    assert log["transactions"][0]["vendor"] == "OpenAI"


def test_reservation_records_validate_against_schema(tmp_path, monkeypatch):
    mod = load_module(tmp_path, monkeypatch)
    quote = run(mod.quote_spend("demo", "Vendor", 4, "one_time", "other", "stack@1"))
    reserve = run(
        mod.reserve_spend(
            quote["quote_id"],
            "auth-schema-001",
            "2099-01-01T00:00:00+00:00",
            project_slug="demo",
            category="other",
            max_authorized_amount_usd=4,
        )
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(reserve["reservation"])
