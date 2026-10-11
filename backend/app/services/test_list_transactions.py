"""B08 flow queries through the gateway: ownership, range, bank clock and completeness."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.contracts.bank import (
    BalanceSnapshot, OperationResult, PayeeDisplay, SavedPayee, TransferReceipt,
)
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.services.mock_bank.flow_seeds import build_flow_rows
from app.services.test_bank import DEMO_SECRET, context
from app.storage import StoragePaths
from app.storage.mock_bank.repository import MockBankStore

BEIJING = timezone(timedelta(hours=8))
NOW = datetime(2026, 10, 12, 10, 0, tzinfo=BEIJING)
START = datetime(2026, 9, 30, 0, 0, tzinfo=BEIJING)
END = datetime(2026, 10, 2, 0, 0, tzinfo=BEIJING)
INSIDE = datetime(2026, 10, 1, 9, 0, tzinfo=BEIJING)


class Clock:
    def __init__(self, at):
        self.at = at

    def __call__(self):
        return self.at

    def advance(self, **delta):
        self.at = self.at + timedelta(**delta)


def ready(tmp_path, at=NOW):
    clock = Clock(at)
    bank = MockBankService(
        MockBankStore(StoragePaths(tmp_path).bank), demo_secret=DEMO_SECRET, clock=clock,
    )
    return bank, BankGateway(bank, authorize_transfer=lambda *args: True), clock


def ledger_row(**overrides):
    return {
        "transaction_id": "TX1", "account_id": "A1", "user_id": "U1",
        "amount_fen": 3200, "direction": "outflow", "nature": "consumption",
        "category": "dining", "occurred_at": "2026-09-30T12:30:00+08:00",
        "counterparty_id": "M1", "counterparty_name": "楼下面馆",
        "counterparty_account_masked": None, "channel": "快捷支付", "summary": "午餐",
        "original_transaction_id": None, "original_occurred_at": None,
    } | overrides


def test_gateway_returns_complete_rows_with_the_bank_clock(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    bank.store.seed_ledger_rows([
        ledger_row(transaction_id="TX2"),
        ledger_row(transaction_id="TX1", occurred_at="2026-10-01T08:00:00+08:00"),
    ])
    result = gateway.list_transactions(context(), "A1", START, END)
    assert result.kind == "ok"
    assert [row.transaction_id for row in result.data.transactions] == ["TX2", "TX1"]
    assert result.data.as_of == NOW
    first = result.data.transactions[0]
    assert (first.counterparty_name, first.channel, first.summary) == ("楼下面馆", "快捷支付", "午餐")
    assert first.account_id == "A1" and first.amount_fen == 3200
    clock.advance(minutes=5)
    assert gateway.list_transactions(context(), "A1", START, END).data.as_of == NOW + timedelta(minutes=5)
    gateway.close()


def test_half_open_range_keeps_the_start_and_drops_the_end(tmp_path):
    bank, gateway, _ = ready(tmp_path)
    bank.store.seed_ledger_rows([
        ledger_row(transaction_id="AT-START", occurred_at=START.isoformat()),
        ledger_row(transaction_id="BEFORE-END", occurred_at=(END - timedelta(seconds=1)).isoformat()),
        ledger_row(transaction_id="AT-END", occurred_at=END.isoformat()),
    ])
    rows = gateway.list_transactions(context(), "A1", START, END).data.transactions
    assert [row.transaction_id for row in rows] == ["AT-START", "BEFORE-END"]
    gateway.close()


def test_other_users_and_unknown_accounts_are_denied(tmp_path):
    _, gateway, _ = ready(tmp_path)
    for user, account_id in ((context("U2", "S2"), "A1"), (context(), "A9")):
        failure = gateway.list_transactions(user, account_id, START, END)
        assert failure.kind == "error" and failure.error.code == "ACCESS_DENIED"
        assert failure.error.details == {}
    gateway.close()


def test_invalid_arguments_and_the_24_month_boundary(tmp_path):
    _, gateway, clock = ready(tmp_path)
    for start, end in (
        (END, START), (START, START), (START.replace(tzinfo=None), END), (START, END.replace(tzinfo=None)),
    ):
        failure = gateway.list_transactions(context(), "A1", start, end)
        assert failure.kind == "error" and failure.error.code == "INVALID_ARGUMENT"
    earliest = datetime(2024, 10, 12, 10, 0, tzinfo=BEIJING)
    assert gateway.list_transactions(context(), "A1", earliest, END).kind == "ok"
    too_early = earliest - timedelta(seconds=1)
    failure = gateway.list_transactions(context(), "A1", too_early, END)
    assert failure.kind == "error" and failure.error.code == "RANGE_UNSUPPORTED"
    assert failure.error.details == {"earliest_supported_at": earliest.isoformat()}
    gateway.close()


def test_empty_success_is_not_a_failure(tmp_path):
    _, gateway, clock = ready(tmp_path)
    empty = gateway.list_transactions(context(), "A1", START, END)
    assert empty.kind == "ok" and empty.data.transactions == [] and empty.data.as_of == clock()
    gateway.close()


def test_runtime_transfer_facts_come_from_the_bank_receipt(tmp_path):
    bank, gateway, _ = ready(tmp_path)
    operation_id, transaction_id = uuid4(), "TX-TRANSFER"
    receipt = TransferReceipt(
        transaction_id=transaction_id, payer_account_id="A1",
        payee=PayeeDisplay(payee_id="A2", name_masked="王*", account_masked="****0002",
                           remark="妈妈", bank_name="模拟银行"),
        amount_fen=50000, fee_fen=0, arrival_mode="instant", completed_at=NOW,
        balance=BalanceSnapshot(account_id="A1", book_balance_fen=5950000, frozen_balance_fen=0,
                                available_balance_fen=5950000, as_of=NOW),
    )
    result = OperationResult[TransferReceipt](
        operation_id=operation_id, operation_type="bank.submit_transfer", operation_status="succeeded",
        recorded_at=NOW, updated_at=NOW, receipt=receipt, failure=None,
    )
    bank.store.commit_operation(
        "U1", str(operation_id), "bank.submit_transfer", {"payer_account_id": "A1"}, "succeeded",
        result.model_dump(mode="json"), NOW.isoformat(), [],
        [(transaction_id, "A1", 50000, "outflow", "transfer", "transfer", INSIDE.isoformat())],
    )
    rows = gateway.list_transactions(context(), "A1", START, END).data.transactions
    assert [row.transaction_id for row in rows] == [transaction_id]
    assert (rows[0].counterparty_id, rows[0].counterparty_name, rows[0].counterparty_account_masked) == (
        "A2", "王*", "****0002")
    assert (rows[0].channel, rows[0].summary, rows[0].nature, rows[0].category) == (
        None, "转账", "transfer", "transfer")
    gateway.close()


def test_unreadable_ledger_row_fails_the_query_instead_of_dropping_it(tmp_path):
    bank, gateway, _ = ready(tmp_path)
    operation_id = uuid4()
    bank.store.commit_operation(
        "U1", str(operation_id), "bank.submit_transfer", {"payer_account_id": "A1"}, "succeeded",
        {"operation_status": "succeeded"}, NOW.isoformat(), [],
        [("TX-BROKEN", "A1", 50000, "outflow", "transfer", "transfer", INSIDE.isoformat())],
    )
    failure = gateway.list_transactions(context(), "A1", START, END)
    assert failure.kind == "error" and failure.error.code == "BANK_UNAVAILABLE"
    assert failure.error.details == {}
    gateway.close()


def test_refund_without_its_original_fails_instead_of_raising(tmp_path):
    bank, gateway, _ = ready(tmp_path)
    bank.store.seed_ledger_rows([ledger_row(
        transaction_id="TX-REFUND", nature="refund", direction="inflow",
        occurred_at=INSIDE.isoformat(),
    )])
    failure = gateway.list_transactions(context(), "A1", START, END)
    assert failure.kind == "error" and failure.error.code == "BANK_UNAVAILABLE"
    gateway.close()


def test_flow_seed_ids_follow_the_bank_month():
    this_month = [row["transaction_id"] for row in build_flow_rows(NOW)]
    same_day = [row["transaction_id"] for row in build_flow_rows(NOW + timedelta(hours=3))]
    next_month = [row["transaction_id"] for row in build_flow_rows(NOW + timedelta(days=25))]
    assert this_month == same_day
    assert not set(this_month) & set(next_month)


def test_seed_flow_history_is_idempotent_and_covers_the_demo_scenarios(tmp_path):
    bank, gateway, clock = ready(tmp_path)
    written = bank.seed_flow_history()
    assert written > 0
    assert bank.seed_flow_history() == 0
    rows = bank.store.list_ledger("U1", "A1") + bank.store.list_ledger("U1", "A5")
    assert len(rows) == written
    assert {"dining", "transport", "medical", "shopping", "housing", "other"} <= {
        row["category"] for row in rows}
    assert any(row["nature"] == "interest" for row in rows)
    assert any(row["channel"] is None and row["nature"] == "consumption" for row in rows)
    refunds = [row for row in rows if row["nature"] == "refund"]
    assert refunds and all(row["original_transaction_id"] for row in refunds)
    occurred = [datetime.fromisoformat(row["occurred_at"]) for row in rows]
    assert max(occurred) <= clock()
    assert any(at.month == clock().month for at in occurred)
    transfers_out = [at for at, row in zip(occurred, rows)
                     if row["nature"] == "transfer" and row["direction"] == "outflow"]
    assert transfers_out and all(at.date() != clock().date() for at in transfers_out)
    assert gateway.list_transactions(context(), "A1", START, END).kind == "ok"
    gateway.close()
