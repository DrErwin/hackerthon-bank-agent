"""Prepare isolated S01/P01 bank facts; serve the real app without changing risk facts."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
from unittest.mock import patch

from app.agent_platform.local_demo import build_runtime, load_config
from app.api.app import ApiConfig, create_app
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.flow_seeds import build_flow_rows, shift_months
from app.storage.mock_bank.repository import BankAccount, MockBankStore


WORKSPACE = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
VERSION = "v05-cross-core-facts-1"
RISK_FIELDS = ("facts_version", "read_fixture", "transfer_fixtures")


def risk_digest(config) -> str:
    # A provenance check only: a matching digest is not a risk approval.
    facts = config.model_dump(mode="json", include=set(RISK_FIELDS))
    return hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()


def seed_case(bank: MockBankService, as_of: datetime) -> int:
    """Only initial bank records: no risk signals, no execution/confirmation bypass."""
    written = bank.store.seed_ledger_rows(build_flow_rows(
        as_of, seeds_dir=FIXTURES, filename="core-flows.json"))
    # The two cancellable mandates already come from the bank's own demo seeds.
    # Add one still-used agreement to exercise the approved keep-one branch.
    with closing(sqlite3.connect(bank.store.path)) as connection, connection:
        connection.execute("""INSERT OR IGNORE INTO bank_subscriptions (
            mandate_id,user_id,account_id,account_masked,merchant_id,merchant_name,
            service_name,amount_fen,cycle,next_billing_at,last_billed_at,status,
            signed_at,cancelled_at,cancel_operation_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            "cross_keep", "U1", "A1", "****0001", "M_CROSS_PHONE", "模拟通信",
            "仍在使用的通信套餐", 2000, "monthly",
            (as_of + timedelta(days=7)).isoformat(), shift_months(as_of, 1).isoformat(),
            "active", shift_months(as_of, 12).isoformat(), None, None,
        ))
    return written


def prepare_case(source: Path, case: str, run_id: str, *, workspace=WORKSPACE) -> Path:
    if case not in {"XL-S01", "XL-P01"} or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}", run_id):
        raise ValueError("INVALID_CASE_OR_RUN_ID")
    workspace = Path(workspace).resolve()
    scope = workspace / ".mnemon" / "v05-cross-e2e"
    directory = scope / case / run_id
    # Refuse even a local symlink pointing at another chat's data.
    if directory.resolve() != directory:
        raise ValueError("RUN_DIRECTORY_NOT_ISOLATED")
    source_config = load_config(source)
    directory.mkdir(parents=True, exist_ok=False)  # never reuse/reset an old run
    as_of = datetime.now(timezone(timedelta(hours=8)))  # same calendar as the demo bank
    config = source_config.model_dump(mode="json")
    for name in ("api_key", "api_secret", "bank_secret", "admin_key"):
        config[name] = (source_config.api_key.get_secret_value() if name == "api_key"
                        else secrets.token_hex(32))
    config["data_directory"] = str(directory / "data")
    config["origins"] = ["http://127.0.0.1:5265", "http://localhost:5265"]
    config_path = directory / ".env.case.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    copied = load_config(config_path)
    store = MockBankStore(copied.data_directory / "mock_bank.sqlite3")
    store.seed_account(BankAccount("A1", "U1", "class_i", "active", 500_000, 0, 0))
    bank = MockBankService(store, demo_secret=copied.bank_secret.get_secret_value().encode())
    seed_case(bank, as_of)
    manifest = {
        "version": VERSION, "case": case, "as_of": as_of.isoformat(),
        "fixture_sha256": hashlib.sha256((FIXTURES / "core-flows.json").read_bytes()).hexdigest(),
        "risk_config_sha256": risk_digest(copied),
        "risk_config_preserved": risk_digest(copied) == risk_digest(source_config),
        "risk_approval": "not_granted_by_fixture_preparation",
        "expected": {
            "payer": "A1", "income_fen": 500_000, "reserve_fen": 150_000,
            "own_transfer": {"account_id": "A5", "amount_fen": 250_000},
            "family_transfer": {"payee_id": "A4", "amount_fen": 100_000},
            "S01_cancel": ["sub_001", "sub_002"], "S01_keep": ["cross_keep"],
            "P01_cancel": ["sub_002"],
            "previous_month_consumption_fen": 28_400,
            "comparison_month_consumption_fen": 18_400,
        },
        "model": "not_run", "http": "not_run", "page_e2e": "not_run",
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return directory


def create_case_app(directory: Path, *, workspace=WORKSPACE):
    """Use scenario seeds at startup; all model, API, bank and gate code stays real."""
    directory = directory.absolute()
    scope = Path(workspace).resolve() / ".mnemon" / "v05-cross-e2e"
    if directory.resolve() != directory or not directory.is_relative_to(scope):
        raise ValueError("RUN_DIRECTORY_NOT_ISOLATED")
    config = load_config(directory / ".env.case.json")
    if config.data_directory.resolve() != directory / "data":
        raise ValueError("CASE_DATA_DIRECTORY_MISMATCH")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if risk_digest(config) != manifest["risk_config_sha256"]:
        raise ValueError("RISK_CONFIG_CHANGED_REPREPARE_WITH_NEW_RUN_ID")
    if hashlib.sha256((FIXTURES / "core-flows.json").read_bytes()).hexdigest() != manifest["fixture_sha256"]:
        raise ValueError("FIXTURE_CHANGED_REPREPARE_WITH_NEW_RUN_ID")
    as_of = datetime.fromisoformat(manifest["as_of"])
    # This is a startup-only data seam. The ordinary loader would add a salary
    # alongside the selected 5000 pension; no bank response or rule is mocked.
    # Single-process build ends the patch before handling any request.
    with patch.object(MockBankService, "seed_flow_history", lambda bank: seed_case(bank, as_of)):
        runtime = build_runtime(config)
    return create_app(runtime, ApiConfig(
        secret=config.api_secret.get_secret_value().encode(),
        demo_user_id=config.demo_user_id, demo_round_id=config.demo_round_id,
        admin_user_id=config.admin_actor_id, admin_key=config.admin_key.get_secret_value(),
        origins=tuple(config.origins),
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("case", choices=("XL-S01", "XL-P01"))
    prepare.add_argument("--config", required=True, type=Path)
    prepare.add_argument("--run-id", required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--directory", required=True, type=Path)
    serve.add_argument("--port", type=int, default=8165)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            directory = prepare_case(args.config, args.case, args.run_id)
            print(json.dumps({"directory": str(directory), "bank_seed": "prepared",
                              "risk_approval": "not_granted", "model": "not_run",
                              "http": "not_run", "page_e2e": "not_run"}))
        else:
            import uvicorn
            uvicorn.run(create_case_app(args.directory), host="127.0.0.1",
                        port=args.port, workers=1, access_log=False)
    except FileExistsError:
        parser.exit(1, "RUN_ALREADY_EXISTS; use a new run-id and preserve the old batch\n")
    except Exception:
        # Config/library errors can echo full input. Never print the exception
        # or fall back to another model, shared database or risk scenario.
        parser.exit(1, "CASE_PREPARATION_OR_START_FAILED; keep the run directory for diagnosis\n")


if __name__ == "__main__":
    main()
