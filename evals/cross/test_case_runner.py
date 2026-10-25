"""Fixture integrity and isolation, never a claim that S01/P01 E2E passed."""

from datetime import datetime
import json
from pathlib import Path
import sqlite3

import httpx
import pytest

from app.agent_platform.local_demo import load_config
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.flow_seeds import shift_months
from app.storage.mock_bank.repository import MockBankStore
from evals.cross.case_runner import create_case_app, main, prepare_case, risk_digest


@pytest.fixture
def source(tmp_path):
    sample = Path(__file__).resolve().parents[2] / "backend/app/agent_platform/local_demo.example.json"
    values = json.loads(sample.read_text(encoding="utf-8"))
    values.update(api_key="DO-NOT-PRINT-API-KEY", api_secret="a" * 32,
                  bank_secret="b" * 32, admin_key="c" * 32,
                  data_directory=str(tmp_path / "shared-do-not-touch"))
    # Unknown dimensions must remain unknown, including the empty case.
    values["read_fixture"]["signals"] = []
    values["read_fixture"]["checked_signals"] = []
    values["transfer_fixtures"] = []
    path = tmp_path / "source.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def bank_for(directory):
    config = load_config(directory / ".env.case.json")
    return MockBankService(MockBankStore(config.data_directory / "mock_bank.sqlite3"),
                           demo_secret=config.bank_secret.get_secret_value().encode())


@pytest.mark.parametrize("case", ["XL-S01", "XL-P01"])
def test_prepare_populates_real_queryable_facts_and_zero_operations(tmp_path, source, case):
    directory = prepare_case(source, case, "batch1", workspace=tmp_path)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    at = datetime.fromisoformat(manifest["as_of"])
    bank = bank_for(directory)
    active = bank.list_subscriptions("U1", "A1", "active").data.mandates
    assert {item.mandate_id for item in active} == {"sub_001", "sub_002", "cross_keep"}
    assert {item.mandate_id: item.amount_fen for item in active} == {
        "sub_001": 2500, "sub_002": 3900, "cross_keep": 2000}
    current_start = at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prior_start = shift_months(current_start, 1)
    comparison_start = shift_months(current_start, 2)
    current = bank.list_transactions("U1", "A1", current_start, at).data.transactions
    income = [row for row in current if row.direction == "inflow"]
    assert [(row.summary, row.amount_fen) for row in income] == [("养老金到账", 500_000)]
    for start, end, expected in ((prior_start, current_start, 28_400),
                                 (comparison_start, prior_start, 18_400)):
        result = bank.list_transactions("U1", "A1", start, end)
        assert result.kind == "ok"
        assert sum(row.amount_fen for row in result.data.transactions
                   if row.nature == "consumption") == expected
    assert bank.get_account("U1", "A1").data.book_balance_fen == 500_000
    assert bank.get_account("U1", "A5").data.book_balance_fen == 0
    assert "A4" in {item.payee_id for item in bank.list_payees("U1").data.payees}
    with sqlite3.connect(bank.store.path) as connection:
        assert connection.execute("SELECT count(*) FROM bank_operations").fetchone()[0] == 0
    assert manifest["model"] == manifest["http"] == manifest["page_e2e"] == "not_run"


def test_copies_risk_facts_without_filling_unknowns_or_touching_source(tmp_path, source):
    original = source.read_bytes()
    directory = prepare_case(source, "XL-P01", "risk-unavailable", workspace=tmp_path)
    copied = load_config(directory / ".env.case.json")
    assert risk_digest(copied) == risk_digest(load_config(source))
    assert copied.read_fixture.checked_signals == []
    assert copied.transfer_fixtures == []
    assert not (tmp_path / "shared-do-not-touch").exists()
    assert source.read_bytes() == original
    assert copied.api_secret != load_config(source).api_secret
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["risk_approval"] == "not_granted_by_fixture_preparation"


def test_refuses_existing_batch_without_resetting_its_bank(tmp_path, source):
    directory = prepare_case(source, "XL-S01", "preserved", workspace=tmp_path)
    database = directory / "data/mock_bank.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE accounts SET book_balance_fen=123 WHERE account_id='A1'")
    config_bytes = (directory / ".env.case.json").read_bytes()
    with pytest.raises(FileExistsError):
        prepare_case(source, "XL-S01", "preserved", workspace=tmp_path)
    assert (directory / ".env.case.json").read_bytes() == config_bytes
    assert bank_for(directory).get_account("U1", "A1").data.book_balance_fen == 123


def test_real_startup_keeps_case_history_and_finished_state_on_restart(tmp_path, source, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("No model/network call belongs in this preparation test")
    monkeypatch.setattr(httpx.Client, "send", no_network)
    directory = prepare_case(source, "XL-S01", "restart", workspace=tmp_path)
    for index in range(2):
        app = create_case_app(directory, workspace=tmp_path)
        runtime = app.state.api.runtime
        bank = runtime.gateway._bank
        rows = bank.store.list_ledger("U1", "A1")
        assert len(rows) == 12  # no additional default salary, including on restart
        assert sum(row["amount_fen"] for row in rows if row["direction"] == "inflow") == 500_000
        if index == 0:
            # Represent a persisted completed action; the seeder must not reactivate it.
            with sqlite3.connect(bank.store.path) as connection:
                connection.execute("""UPDATE bank_subscriptions SET status='cancelled',
                    next_billing_at=NULL,cancelled_at=signed_at WHERE mandate_id='cross_keep'""")
                connection.execute("UPDATE accounts SET book_balance_fen=150000 WHERE account_id='A1'")
        else:
            assert "cross_keep" not in {item.mandate_id for item in
                                        bank.list_subscriptions("U1", "A1", "active").data.mandates}
            assert bank.get_account("U1", "A1").data.book_balance_fen == 150_000
        runtime.close()


def test_serve_refuses_changed_risk_configuration(tmp_path, source):
    directory = prepare_case(source, "XL-P01", "unchanged-risk", workspace=tmp_path)
    path = directory / ".env.case.json"
    values = json.loads(path.read_text(encoding="utf-8"))
    values["read_fixture"]["checked_signals"] = ["familiar_device"]
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(ValueError, match="RISK_CONFIG_CHANGED"):
        create_case_app(directory, workspace=tmp_path)


@pytest.mark.parametrize("run_id", ["../shared", "x/y", ""])
def test_run_id_cannot_select_shared_paths(tmp_path, source, run_id):
    with pytest.raises(ValueError, match="INVALID_CASE_OR_RUN_ID"):
        prepare_case(source, "XL-S01", run_id, workspace=tmp_path)
    assert not (tmp_path / ".mnemon").exists()


def test_cli_invalid_config_never_echoes_credentials(tmp_path, monkeypatch, capsys):
    source = tmp_path / "invalid.json"
    source.write_text('{"api_key":"DO-NOT-PRINT-THIS"}', encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["case_runner.py", "prepare", "XL-S01",
                                   "--config", str(source), "--run-id", "invalid-config"])
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert "DO-NOT-PRINT" not in captured.out + captured.err
    assert "CASE_PREPARATION_OR_START_FAILED" in captured.err
