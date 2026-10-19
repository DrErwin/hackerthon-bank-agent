"""02/L03 report-only formatting of proven L01 statistics.

Private preparation, not a registered public report capability. This module
never persists reports, issues download links, verifies identity or shares to
third parties. The platform owns F21--F24 storage/export and authorization.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.contracts.bills import SpendingSummary, BillReport

Purpose = Literal["self_view", "print", "share_request"]


def average_per_30_days(gross_fen: int, days: int) -> int | None:
    """Contract §5.9: gross spending ×30 ÷ actual Beijing calendar days.

    Integer-fen half-up rounding occurs once at the end. Refunds do not reduce
    this number; they remain visible separately in the net amount.
    """
    if type(gross_fen) is not int or gross_fen < 0:
        raise ValueError("invalid_gross")
    if type(days) is not int or days < 0:
        raise ValueError("invalid_statistical_days")
    if days == 0:
        return None
    numerator = gross_fen * 30
    return (2 * numerator + days) // (2 * days)


def plain_summary(summary: "SpendingSummary") -> str:
    """Spoken explanation of frozen 1/2/3 blocks; no trends/anomaly claim."""
    if summary.transaction_count == 0:
        return "查询范围内没有交易记录。"
    gross = summary.consumption_gross_fen
    refund = summary.consumption_refund_fen
    net = summary.consumption_net_fen
    if net != gross - refund:
        raise ValueError("invalid_net_equation")
    result = (f"本次共查询到{summary.transaction_count}笔交易；消费支出{gross // 100}元"
              f"{gross % 100:02d}分，退款{refund // 100}元{refund % 100:02d}分，"
              f"净消费{'负' if net < 0 else ''}{abs(net) // 100}元{abs(net) % 100:02d}分。")
    if summary.comparison is not None:
        delta = summary.comparison.delta_fen
        result += f"对照期净消费差额{'负' if delta < 0 else ''}{abs(delta) // 100}元{abs(delta) % 100:02d}分。"
    return result


def report_from_verified_summary(summary: "SpendingSummary", *, report_id: str,
                                 statistical_days: int, generated_at: datetime,
                                 purpose: Purpose = "self_view") -> "BillReport":
    """Create a typed BillReport after caller's *trusted* complete L01 read.

    The service, not a client/model, supplies report_id, generated_at and
    statistical_days computed from authoritative scope/as_of/current clock.
    ``share_request`` changes wording intent only; this function never shares.
    """
    from app.contracts.bills import BillReport, SpendingSummary
    if not isinstance(summary, SpendingSummary):
        raise TypeError("trusted_spending_summary_required")
    if purpose not in ("self_view", "print", "share_request"):
        raise ValueError("invalid_purpose")
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("timezone_required")
    avg = average_per_30_days(summary.consumption_gross_fen, statistical_days)
    return BillReport(report_id=report_id, scope=summary.scope, summary=summary,
        spoken_summary=plain_summary(summary), monthly_average_fen=avg,
        statistical_days=statistical_days,
        average_basis="按统计天数折算，每月30天；不预测未来实际支出" if statistical_days else "没有有效统计天数，无法折算月均",
        generated_at=generated_at)
