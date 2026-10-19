"""Typed L03 business preparation; F21/F22/F24 integration is platform-owned."""
from datetime import datetime, timedelta

import pytest

from app.contracts.bills import BillReport
from app.modules.bills.report_service import BillsReportService, covered_days
from app.modules.bills.test_public import Reads, transaction, CTX, START, END, NOW


def report_service(rows=(), *, accounts=("a1",)):
    reads = Reads(rows, accounts=accounts)
    return BillsReportService(reads, lambda: NOW), reads


def scope(end=END):
    return {"account_ids": ["a1"], "start_at": START.isoformat(), "end_at": end.isoformat()}


def test_l03_20_days_gross_refund_and_report_blocks():
    end = START + timedelta(days=20)
    refund = transaction("ref", amount=20000, category="dining",
        nature="refund", direction="inflow", at=START + timedelta(days=1),
        original=transaction(amount=60000))
    service, reads = report_service([transaction(amount=60000), refund])
    result = service.generate_report(CTX, {"scope": scope(end),
        "purpose": "self_view"})
    assert result.status == "succeeded" and isinstance(result.data, BillReport)
    assert result.data.summary.consumption_net_fen == 40000
    assert result.data.statistical_days == 20
    assert result.data.monthly_average_fen == 90000
    assert result.data.average_basis.startswith("按统计天数")
    assert result.data.report_id
    assert not any(k == "write" for k in reads.calls)


def test_share_request_does_not_share_or_grant_download():
    service, reads = report_service([transaction()])
    result = service.generate_report(CTX, {"scope": scope(),
        "purpose": "share_request"})
    assert result.status == "succeeded"
    assert isinstance(result.data, BillReport)
    assert result.allowed_actions == []
    assert not hasattr(result.data, "download_url")
    assert not hasattr(result.data, "shared_with")


def test_report_invalid_scope_or_extra_data_rejected_before_bank():
    service, reads = report_service()
    r = service.generate_report(CTX, {"scope": scope(), "purpose": "share_request",
                                       "share_to_user": "someone_else"})
    assert r.status == "failed" and r.error.code == "INVALID_ARGUMENT"
    assert reads.calls == []


def test_report_failure_is_not_blank_success():
    service, reads = report_service([transaction()])
    reads.failure = lambda *_: True
    result = service.generate_report(CTX, {"scope": scope(), "purpose": "print"})
    assert result.status == "failed"
    assert result.data is None
    assert result.error.upstream_code == "CALL_TIMEOUT"


def test_statistical_days_beijing_half_open_and_asof():
    a = datetime.fromisoformat("2026-09-01T00:00:00+08:00")
    end = datetime.fromisoformat("2026-09-21T00:00:00+08:00")
    now = datetime.fromisoformat("2026-10-02T12:00:00+08:00")
    o = type("Scope", (), {"start_at": a, "end_at": end})()
    assert covered_days(o, now, now) == 20
    end2 = datetime.fromisoformat("2026-09-21T12:00:00+08:00")
    o.end_at = end2
    assert covered_days(o, now, now) == 21
    assert covered_days(o, a, now) == 0


def test_report_comparison_inherits_same_account_set():
    service, reads = report_service([transaction()])
    bad = service.generate_report(CTX, {"scope": scope(), "purpose": "self_view",
        "comparison_scope": {"account_ids": ["a2"], "start_at": START,
                             "end_at": END}})
    assert bad.status == "failed" and bad.error.code == "INVALID_ARGUMENT"
    assert reads.calls == []


def test_l03_public_entry_registers_separately_and_produces_bill_report():
    from uuid import uuid4
    from app.agent_platform.registry import CapabilityRegistry
    from app.contracts.platform import StartTransferInput
    from app.modules.bills.entry import register_bills, register_bills_report
    from app.modules.bills.test_public import Saver

    reads = Reads([transaction()], accounts=("a1",))
    registry = CapabilityRegistry()
    factory = lambda trusted, trace: reads
    register_bills(registry, factory, lambda: NOW)
    register_bills_report(registry, factory, lambda: NOW)
    assert {item["name"] for item in registry.public_catalog()} == {
        "bills.summarize", "bills.generate_report"
    }

    report_entry = registry.get("bills.generate_report").factory(CTX, Saver(), None)
    result = report_entry.start(CTX, StartTransferInput(
        request_id=uuid4(), intent_text="2026年9月所有账户账单报告"
    ), thread_id="l03-case")
    assert result.status == "succeeded", result
    assert isinstance(result.data, BillReport)
    assert result.data.summary.consumption_gross_fen == 50000
    assert result.data.scope.account_ids == ["a1"]

    summary_entry = registry.get("bills.summarize").factory(CTX, Saver(), None)
    summary = summary_entry.start(CTX, StartTransferInput(
        request_id=uuid4(), intent_text="2026年9月所有账户账单"
    ), thread_id="l01-case")
    assert summary.status == "succeeded"
    assert not isinstance(summary.data, BillReport)


def test_l03_report_clarification_survives_restart_and_share_is_not_authorization():
    from uuid import uuid4
    from app.contracts.platform import StartTransferInput
    from app.modules.bills.entry import bills_report_factory
    from app.modules.bills.test_public import Saver

    saver = Saver()
    reads = Reads([transaction()], accounts=("a1",))
    factory = bills_report_factory(lambda trusted, trace: reads, lambda: NOW)
    request = StartTransferInput(request_id=uuid4(), intent_text="给子女看账单报告")
    first = factory(CTX, saver, None).start(CTX, request, thread_id="l03-share")
    assert first.status == "waiting_input"
    assert not reads.calls
    month = next(x for x in first.interaction.options if x.label == "上月")
    second = factory(CTX, saver, None).resume(
        CTX, {"choice": month.id}, thread_id="l03-share")
    assert second.status == "waiting_input"
    account = next(x for x in second.interaction.options if x.label == "所有本人账户")
    third = factory(CTX, saver, None).resume(
        CTX, {"choice": account.id}, thread_id="l03-share")
    assert third.status == "succeeded"
    assert isinstance(third.data, BillReport)
    assert third.allowed_actions == []
    assert "share_request" not in third.model_dump_json()


def test_l03_this_year_report_uses_trusted_2026_to_date_not_future():
    from uuid import uuid4
    from app.contracts.platform import StartTransferInput
    from app.modules.bills.entry import bills_report_factory, parse_report_period
    from app.modules.bills.test_public import Saver

    assert parse_report_period("查看今年账单报告", NOW) == (
        "2026-01-01T00:00:00+08:00", NOW.isoformat()
    )
    assert parse_report_period("今年和去年比较", NOW) is None
    reads = Reads([transaction()], accounts=("a1",))
    e = bills_report_factory(lambda trusted, trace: reads, lambda: NOW)(CTX, Saver(), None)
    report = e.start(CTX, StartTransferInput(
        request_id=uuid4(), intent_text="今年所有账户账单报告"
    ), thread_id="l03-year-2026")
    assert report.status == "succeeded", report
    assert report.data.scope.start_at.year == 2026
    assert report.data.scope.start_at.month == 1
    assert report.data.scope.end_at == NOW
    assert report.data.summary.consumption_gross_fen == 50000


def test_l03_previous_year_is_whole_year_and_explicit_year_parses():
    from app.modules.bills.entry import parse_report_period

    assert parse_report_period("去年账单报告", NOW) == (
        "2025-01-01T00:00:00+08:00", "2026-01-01T00:00:00+08:00"
    )
    assert parse_report_period("2025年度账单报告", NOW) == (
        "2025-01-01T00:00:00+08:00", "2026-01-01T00:00:00+08:00"
    )
    assert parse_report_period("2027年度账单报告", NOW) is None


@pytest.mark.parametrize("period", [
    "2026年13月", "2026年0月", "今年9月", "0000年", "9999年",
    "跟上月比", "跟上个月比", "跟去年比", "和去年比",
    "9999年9月", "2027年9月", "2026年11月",
    "2026年9月15日", "今年上半年", "2026年9月对比去年",
    "2026年9月上半月", "2026年9月下半月", "2026年9月和10月",
    "本月和9月", "2026年9月及2025年", "2026年9月月底",
    "2026年9月同比", "2026年9月环比", "2026年9月多了多少", "2026年9月少了多少",
])
def test_l03_unsupported_period_never_widens_into_a_year_or_reads_bank(period):
    from uuid import uuid4
    from app.contracts.platform import StartTransferInput
    from app.modules.bills.entry import bills_report_factory, parse_report_period
    from app.modules.bills.test_public import Saver

    assert parse_report_period(period + "账单报告", NOW) is None
    reads = Reads([transaction()], accounts=("a1",))
    entry = bills_report_factory(lambda trusted, trace: reads, lambda: NOW)(CTX, Saver(), None)
    result = entry.start(CTX, StartTransferInput(
        request_id=uuid4(), intent_text=period + "所有账户账单报告"
    ), thread_id="l03-invalid-period")
    assert result.status == "waiting_input" and result.data is None
    assert not reads.calls


@pytest.mark.parametrize("restriction", ["仅餐饮", "只看购物", "餐饮和购物", "不含转账", "明细"])
def test_l03_unavailable_filter_requires_choice_before_whole_report(restriction):
    from uuid import uuid4
    from app.contracts.platform import StartTransferInput
    from app.modules.bills.entry import bills_report_factory
    from app.modules.bills.test_public import Saver

    reads = Reads([
        transaction("meal", amount=7000, category="dining"),
        transaction("shop", amount=50000, category="shopping"),
    ], accounts=("a1",))
    entry = bills_report_factory(lambda trusted, trace: reads, lambda: NOW)(CTX, Saver(), None)
    result = entry.start(CTX, StartTransferInput(request_id=uuid4(),
        intent_text="2026年9月所有账户" + restriction + "账单报告"), thread_id="l03-filter")
    assert result.status == "waiting_input" and result.data is None
    assert not reads.calls
    option = next(o for o in result.interaction.options if o.label == "查看全部类别报告")
    report = entry.resume(CTX, {"choice": option.id,
        "interaction_id": result.interaction.interaction_id}, thread_id="l03-filter")
    assert report.status == "succeeded" and isinstance(report.data, BillReport)
    assert report.data.summary.consumption_gross_fen == 57000


def test_l03_replay_keeps_typed_report_id_without_regeneration():
    from uuid import uuid4
    from app.contracts.platform import StartTransferInput
    from app.modules.bills.entry import bills_report_factory
    from app.modules.bills.test_public import Saver

    reads = Reads([transaction()], accounts=("a1",))
    saver = Saver()
    factory = bills_report_factory(lambda trusted, trace: reads, lambda: NOW)
    request = StartTransferInput(request_id=uuid4(), intent_text="2026年9月所有账户账单报告")
    first = factory(CTX, saver, None).start(CTX, request, thread_id="l03-replay")
    assert first.status == "succeeded" and isinstance(first.data, BillReport)
    calls = list(reads.calls)
    writes = saver.writes
    next_context = CTX.model_copy(update={"run_id": "replay-run"})
    for result in (
        factory(next_context, saver, None).start(next_context, request, thread_id="l03-replay"),
        factory(next_context, saver, None).resume(next_context, {}, thread_id="l03-replay"),
    ):
        assert isinstance(result.data, BillReport)
        assert result.data.report_id == first.data.report_id
        assert result.data == first.data
        assert result.run_id == "replay-run"
    assert reads.calls == calls and saver.writes == writes
