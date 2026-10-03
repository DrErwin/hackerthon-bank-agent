"""JSON bank fixtures preserve default demos and enable isolated evaluations."""

import json
from pathlib import Path
from uuid import uuid4


from app.contracts.bank import ManualPayee, SavedPayee
from app.services.mock_bank import core
from app.services.test_bank import context, ready, DEMO_SECRET
from app.storage.mock_bank.repository import MockBankStore


def test_duplicate_names_and_phone_return_masked_scoped_candidates(tmp_path):
    _, gateway = ready(tmp_path)
    try:
        for name, ids, tails in [
            ("张伟", ["A8", "A9"], ["1111", "2222"]),
            ("李明", ["A10", "A11"], ["3333", "4444"]),
        ]:
            candidates = gateway.list_payees(context(), {"kind": "name", "value": name}).data.payees
            assert [p.payee_id for p in candidates] == ids
            assert [p.account_masked for p in candidates] == ["****" + tail for tail in tails]
            assert gateway.list_payees(context("U2"), {"kind": "name", "value": name}).data.payees == []
        phone = gateway.list_payees(context(), {"kind": "phone", "value": "13812345678"}).data.payees
        assert [p.payee_id for p in phone] == ["A12"]
        assert phone[0].remark is None
        assert "13812345678" not in str(phone[0].model_dump())
    finally:
        gateway.close()


def test_json_numbers_support_exact_search_and_manual_verification(tmp_path):
    _, gateway = ready(tmp_path)
    try:
        seeds = json.loads((Path(core.__file__).parent / "seeds" / "payees.json").read_text(encoding="utf-8"))
        lengths = set()
        for row in seeds:
            if row["payee_id"] not in {"A8", "A9", "A10", "A11", "A12"}:
                continue
            number = row["account_number"]
            lengths.add(len(number))
            candidates = gateway.list_payees(context(), {"kind": "account_number", "value": number}).data.payees
            assert [p.payee_id for p in candidates] == [row["payee_id"]]
            supplied = ManualPayee(kind="manual", account_name=row["name"], account_number=number)
            assert gateway.verify_payee(context(), supplied).data.matched
            assert not gateway.verify_payee(context("U2"), supplied).data.matched
            assert number not in str(candidates[0].model_dump())
        assert lengths == {16, 19}
    finally:
        gateway.close()


def test_evaluation_accounts_are_opt_in_and_preserved_on_restart(tmp_path):
    bank, gateway = ready(tmp_path)
    try:
        assert {a.account_id for a in gateway.list_accounts(context()).data.accounts} == {"A1", "A5"}
        bank.seed_demo(include_evaluation=True)
        assert gateway.get_account(context(), "A6").data.available_balance_fen == 50_000
        assert gateway.get_account(context(), "A8_ACC").data.account_status == "frozen"
        assert gateway.get_account(context("U2"), "A6").error.code == "ACCESS_DENIED"
        payee = SavedPayee(kind="saved", payee_id="A2")
        insufficient = gateway.precheck_transfer(context(), "A6", payee, 50_001).data
        assert insufficient.failure.code == "INSUFFICIENT_FUNDS"
        assert insufficient.failure.details["shortfall_fen"] == 1
        frozen = gateway.submit_transfer(context(), uuid4(), "A8_ACC", payee, 1)
        assert frozen.failure.code == "ACCOUNT_UNAVAILABLE"
        assert bank.store.list_ledger("U1", "A8_ACC") == []
        assert gateway.precheck_transfer(context(), "A6", payee, 50_000).data.can_proceed
        result = gateway.submit_transfer(context(), uuid4(), "A6", payee, 50_000)
        assert result.operation_status == "succeeded"
        reopened = core.MockBankService(MockBankStore(bank.store.path), demo_secret=DEMO_SECRET)
        reopened.seed_demo(include_evaluation=True)
        assert reopened.get_account("U1", "A6").data.available_balance_fen == 0
        assert len(reopened.store.list_ledger("U1", "A6")) == 1
    finally:
        gateway.close()


def test_account_seed_values_are_loaded_from_json_at_seeding(tmp_path, monkeypatch):
    bank, gateway = ready(tmp_path)
    try:
        source = Path(core.__file__).parent / "seeds"
        seeds = tmp_path / "seeds"
        seeds.mkdir()
        rows = json.loads((source / "accounts.json").read_text(encoding="utf-8"))
        row = next(row for row in rows if row["account_id"] == "A6")
        row["book_balance_fen"] = 12345
        (seeds / "accounts.json").write_text(json.dumps(rows), encoding="utf-8")
        monkeypatch.setattr(core, "SEEDS_DIR", seeds)
        bank.seed_demo(include_evaluation=True)
        assert gateway.get_account(context(), "A6").data.available_balance_fen == 12345
    finally:
        gateway.close()
