"""L02 typed API preparation over the same authorized read-only B08 contract."""
from datetime import datetime, timedelta

import pytest

from app.contracts.bank import BankError, QueryFailure
from app.contracts.bills import BillScope
from app.contracts.bills import AnomalyResult, TransactionCandidates
from app.modules.bills.anomaly_service import BillsAnomalyService
from app.modules.bills.test_public import Reads, transaction, CTX, NOW, START, END


def date(value):
    return datetime.fromisoformat(value)


def query_scope(start=START, end=END, account_ids=("a1",)):
    return {"account_ids": list(account_ids),
            "start_at": start.isoformat(), "end_at": end.isoformat()}


def service(rows=(), accounts=("a1",)):
    r=Reads(rows, accounts=accounts)
    return BillsAnomalyService(r, lambda:NOW),r


def test_locate_matches_only_bank_fact_clues():
    p=transaction("hit",amount=50000)
    q=transaction("other",amount=30000)
    svc,reads=service([p,q])
    result=svc.detect(CTX, {"mode":"locate","scope":query_scope(),
        "clues":{"amount_fen":50000,"counterparty_hint":"正常商"}})
    assert result.status=="succeeded"
    assert isinstance(result.data,TransactionCandidates)
    assert [r.transaction_id for r in result.data.candidates]==["hit"]
    assert set(call[0] for call in reads.calls)=={"accounts","transactions"}


def test_locate_empty_is_complete_no_match_not_bank_failure():
    svc,r=service([transaction()])
    result=svc.detect(CTX, {"mode":"locate","scope":query_scope(),
                              "clues":{"amount_fen":1}})
    assert result.status=="succeeded" and result.data.candidates == []


def test_single_observes_exact_transaction_and_four_rule_checks():
    prior=transaction("prior",amount=3000,at=date("2026-08-10T13:00:00+08:00"))
    target=transaction("target",amount=10000,at=date("2026-09-10T23:00:00+08:00"))
    svc,r=service([prior,target])
    result=svc.detect(CTX,{"mode":"single","account_id":"a1",
                          "transaction_id":"target"})
    assert result.status=="succeeded"
    assert isinstance(result.data,AnomalyResult)
    assert result.data.transaction.transaction_id=="target"
    assert [x.rule_id for x in result.data.checks]==[1,2,3,4]
    assert {x.rule_id for x in result.data.findings}>={1,3}
    assert all("盗刷已确认" not in x.evidence for x in result.data.findings)


def test_single_unknown_id_is_failure_not_empty_clearance():
    svc,r=service([transaction()])
    result=svc.detect(CTX,{"mode":"single","account_id":"a1",
                          "transaction_id":"does-not-exist"})
    assert result.status=="failed" and result.data is None
    assert result.error.code=="RECORD_NOT_FOUND"
    assert "查询范围" in result.message


def test_single_does_not_make_up_trusted_kinship():
    target=transaction("target",nature="transfer",amount=10000,
      at=date("2026-09-10T12:00:00+08:00"))
    svc,r=service([target])
    result=svc.detect(CTX,{"mode":"single","account_id":"a1",
                          "transaction_id":"target"})
    assert result.status=="succeeded"
    assert result.data.checks[0].status=="insufficient_data"


def test_scan_only_checks_rule4_and_never_writes():
    dates=["2026-07-10T12:00:00+08:00","2026-08-12T12:00:00+08:00",
           "2026-09-09T12:00:00+08:00"]
    rows=[transaction(str(i),amount=3900,at=date(s)) for i,s in enumerate(dates)]
    svc,r=service(rows)
    result=svc.detect(CTX,{"mode":"scan",
        "scope":query_scope(start=date("2026-07-01T00:00:00+08:00"))})
    assert result.status=="succeeded" and result.data.transaction is None
    assert len(result.data.findings)==1
    assert [x.rule_id for x in result.data.checks]==[4]
    assert not any(call[0] == "write" for call in r.calls)


def test_short_range_scan_stays_insufficient_instead_of_clear():
    svc,r=service([transaction()])
    result=svc.detect(CTX,{"mode":"scan","scope":query_scope()})
    assert result.status=="succeeded"
    assert result.data.checks[0].status=="insufficient_data"


def test_unowned_account_is_rejected_before_transaction_read():
    svc,r=service([transaction()])
    result=svc.detect(CTX,{"mode":"locate",
        "scope":query_scope(account_ids=("a1","other")),
        "clues":{"amount_fen":50000}})
    assert result.status=="failed" and result.error.code=="ACCESS_DENIED"
    assert not any(call[0] == "transactions" for call in r.calls)


def test_client_supplied_facts_and_permissions_rejected_before_bank_call():
    svc,r=service([transaction()])
    result=svc.detect(CTX,{"mode":"single","account_id":"a1",
        "transaction_id":"x","amount_fen":9999,"verified":True})
    assert result.status=="failed" and result.error.code=="INVALID_ARGUMENT"
    assert r.calls==[]


def test_failed_B08_never_reports_clean_scan():
    svc,r=service([transaction()])
    r.failure=lambda *_:True
    result=svc.detect(CTX,{"mode":"scan","scope":query_scope(
        start=date("2026-07-01T00:00:00+08:00"))})
    assert result.status=="failed" and result.data is None


def test_selected_scope_rereads_target_and_exact_three_month_history():
    target = transaction("selected", at=date("2026-09-10T06:00:00+08:00"))
    svc, reads = service([target])
    scope = BillScope.model_validate(query_scope())
    result = svc.detect(CTX, {"mode": "single", "account_id": "a1",
                              "transaction_id": "selected"}, located_scope=scope)
    assert result.status == "succeeded", result
    assert result.data.transaction == target
    calls = [call for call in reads.calls if call[0] == "transactions"]
    assert [(call[2], call[3]) for call in calls] == [
        (START, END), (date("2026-06-10T06:00:00+08:00"), target.occurred_at + timedelta(microseconds=1))]
    assert result.data.checks[2].status == "evaluated" and result.data.checks[2].reason == "not_matched"


def test_scoped_missing_target_is_not_found_without_replacing_it():
    svc, reads = service([transaction()])
    result = svc.detect(CTX, {"mode": "single", "account_id": "a1", "transaction_id": "absent"},
                        located_scope=BillScope.model_validate(query_scope()))
    assert result.error.code == "RECORD_NOT_FOUND" and result.data is None
    assert len([call for call in reads.calls if call[0] == "transactions"]) == 1


def test_standalone_uses_the_bank_bound_and_only_one_retry():
    earliest = date("2025-01-07T04:05:06+08:00")  # bank fact, not a module retention constant
    target = transaction("selected")
    svc, reads = service([target])
    original = reads.transactions
    ranges = []

    def limited(context, account, start, end):
        ranges.append((start, end))
        if start < earliest:
            return QueryFailure(kind="error", error=BankError(code="RANGE_UNSUPPORTED",
                details={"earliest_supported_at": earliest.isoformat(), "unsafe": "secret"}))
        return original(context, account, start, end)

    reads.transactions = limited
    result = svc.detect(CTX, {"mode": "single", "account_id": "a1", "transaction_id": "selected"})
    assert result.status == "succeeded", result
    assert ranges[1][0] == earliest
    assert result.data.transaction == target
    assert "secret" not in result.model_dump_json()


@pytest.mark.parametrize("bound", [None, "invalid", "2026-01-01T00:00:00", "2099-01-01T00:00:00+08:00"])
def test_unusable_bank_bound_requires_locate_without_guessing_or_infinite_retry(bound):
    svc, reads = service()
    calls = []

    def unavailable(*args):
        calls.append(args)
        return QueryFailure(kind="error", error=BankError(code="RANGE_UNSUPPORTED",
                            details={"earliest_supported_at": bound}))

    reads.transactions = unavailable
    result = svc.detect(CTX, {"mode": "single", "account_id": "a1", "transaction_id": "old"})
    assert result.error.code == "BILLS_LOCATE_REQUIRED" and result.data is None
    assert len(calls) == 1


def test_advancing_bank_bound_is_not_silently_narrowed_to_false_not_found():
    svc, reads = service()
    calls = []

    def moving(*args):
        calls.append(args)
        bound = date("2025-01-01T00:00:00+08:00") + timedelta(microseconds=len(calls))
        return QueryFailure(kind="error", error=BankError(code="RANGE_UNSUPPORTED",
                            details={"earliest_supported_at": bound.isoformat()}))

    reads.transactions = moving
    result = svc.detect(CTX, {"mode": "single", "account_id": "a1", "transaction_id": "old"})
    assert result.error.code == "BILLS_LOCATE_REQUIRED" and result.error.upstream_code == "RANGE_UNSUPPORTED"
    assert result.data is None and len(calls) == 2


def test_retention_missing_baseline_is_insufficient_but_target_time_still_checked():
    target = transaction("selected", at=date("2026-09-10T23:00:00+08:00"))
    svc, reads = service([target])
    original = reads.transactions

    def missing_history(context, account, start, end):
        if start < START:
            return QueryFailure(kind="error", error=BankError(code="RANGE_UNSUPPORTED", details={}))
        return original(context, account, start, end)

    reads.transactions = missing_history
    result = svc.detect(CTX, {"mode": "single", "account_id": "a1", "transaction_id": "selected"},
                        located_scope=BillScope.model_validate(query_scope()))
    assert result.status == "succeeded" and result.data.transaction == target
    assert [(check.rule_id, check.status) for check in result.data.checks] == [
        (1, "insufficient_data"), (2, "insufficient_data"), (3, "evaluated"), (4, "insufficient_data")]
    assert [finding.rule_id for finding in result.data.findings] == [3]


def test_inconsistent_history_cannot_replace_bank_target_or_give_complete_result():
    target = transaction("selected")
    svc, reads = service([target])
    original = reads.transactions

    def changed_history(context, account, start, end):
        if start < START:
            reads.rows = [target.model_copy(update={"amount_fen": 1})]
        return original(context, account, start, end)

    reads.transactions = changed_history
    result = svc.detect(CTX, {"mode": "single", "account_id": "a1", "transaction_id": "selected"},
                        located_scope=BillScope.model_validate(query_scope()))
    assert result.error.code == "INCOMPLETE_FACTS" and result.data is None


@pytest.mark.parametrize("bad", ["duplicate", "wrong_account", "after_asof", "future_asof", "cross_account_id"])
def test_bank_integrity_errors_never_produce_complete_candidates(bad):
    target = transaction()
    svc, reads = service([target], accounts=("a1", "a2"))
    if bad == "duplicate":
        reads.extra = target
    elif bad == "wrong_account":
        reads.extra = transaction("foreign", account="foreign")
    elif bad == "after_asof":
        reads.cutoffs = {"a1": START - timedelta(seconds=1)}
    elif bad == "future_asof":
        reads.cutoffs = {"a1": NOW + timedelta(seconds=1)}
    else:
        reads.rows.append(transaction(account="a2"))
    result = svc.detect(CTX, {"mode": "locate", "scope": query_scope(account_ids=("a1", "a2")),
                              "clues": {"amount_fen": 50000}})
    assert result.status == "failed" and result.data is None


def test_one_failed_account_cannot_return_partial_candidates():
    svc, reads = service([transaction()], accounts=("a1", "a2"))
    reads.failure = lambda account, *_: account == "a2"
    result = svc.detect(CTX, {"mode": "locate", "scope": query_scope(account_ids=("a1", "a2")),
                              "clues": {"amount_fen": 50000}})
    assert result.error.upstream_code == "CALL_TIMEOUT" and result.data is None


@pytest.mark.parametrize("start, end, cutoff", [
    ("2026-07-31T00:00:00+08:00", "2026-10-01T00:00:00+08:00", NOW),
    ("2026-08-01T00:00:00+08:00", "2026-11-01T00:00:00+08:00", NOW),
])
def test_partial_or_future_months_do_not_supply_a_clear_scan_baseline(start, end, cutoff):
    svc, reads = service()
    reads.cutoffs = {"a1": cutoff}
    result = svc.detect(CTX, {"mode": "scan", "scope": query_scope(start=date(start), end=date(end))})
    assert result.data.checks[0].status == "insufficient_data" and result.data.findings == []


def test_three_real_monthly_charges_are_reported_even_with_partial_endpoint_months():
    rows = [transaction(str(index), amount=3900, at=date(value)) for index, value in enumerate([
        "2026-07-31T12:00:00+08:00", "2026-08-31T12:00:00+08:00", "2026-09-30T12:00:00+08:00"])]
    svc, reads = service(rows)
    result = svc.detect(CTX, {"mode": "scan", "scope": query_scope(start=date("2026-07-31T00:00:00+08:00"))})
    assert result.data.checks[0].status == "evaluated" and len(result.data.findings) == 1


def test_public_single_counts_prior_inflow_as_a_known_counterparty():
    prior = transaction("prior-inflow", nature="transfer", direction="inflow", amount=100000,
                        at=date("2026-08-10T12:00:00+08:00"))
    target = transaction("outflow", nature="transfer", amount=100)
    svc, reads = service([prior, target])
    result = svc.detect(CTX, {"mode": "single", "account_id": "a1", "transaction_id": "outflow"},
                        located_scope=BillScope.model_validate(query_scope()))
    assert result.status == "succeeded"
    assert result.data.checks[1].reason == "not_matched"
    assert not any(finding.rule_id == 2 for finding in result.data.findings)


def test_public_scan_reports_missing_merchant_identity_after_complete_bank_reads():
    rows = [transaction(str(month), at=date(f"2026-{month:02}-10T12:00:00+08:00"))
            .model_copy(update={"counterparty_id": None}) for month in (7, 8, 9)]
    svc, reads = service(rows)
    result = svc.detect(CTX, {"mode": "scan", "scope": query_scope(start=date("2026-07-01T00:00:00+08:00"))})
    assert result.status == "succeeded" and result.data.checks[0].status == "insufficient_data"
    assert result.data.checks[0].reason == "merchant_identity_missing"
    assert result.data.findings == [] and "缺少商户标识" in result.message
