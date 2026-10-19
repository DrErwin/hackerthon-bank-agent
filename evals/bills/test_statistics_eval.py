"""Golden arithmetic assertions, never a claim of L01/Agent/HTTP acceptance."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from app.modules.bills._statistics import (
    AccountBatch, FactsError, LedgerRow, Period, Snapshot,
    assemble, compare, monthly_average, select_rows, statistical_days, totals,
)

DIRECTORY = Path(__file__).parent
CASES = json.loads((DIRECTORY / "fixtures/arithmetic-cases.json").read_text(encoding="utf-8"))["cases"]
CASE_MAP = json.loads((DIRECTORY / "fixture_map.json").read_text(encoding="utf-8"))
assert len({c["id"] for c in CASES}) == len(CASES), "duplicate fixture ids"
assert CASE_MAP == {c["id"]: c["case_ids"] for c in CASES}, "fixture and mapping differ"
assert all(c["case_ids"] for c in CASES), "every arithmetic sample needs a business link"


@dataclass(frozen=True)
class EvaluationState:
    snapshot: Snapshot
    now: datetime


def ledger_rows(rows: list[dict[str, Any]]) -> tuple[LedgerRow, ...]:
    parsed = []
    for raw in rows:
        fields = dict(raw)
        fields["occurred_at"] = datetime.fromisoformat(raw["occurred_at"])
        fields["original_occurred_at"] = (
            datetime.fromisoformat(raw["original_occurred_at"])
            if raw["original_occurred_at"] is not None else None
        )
        parsed.append(LedgerRow(**fields))
    return tuple(parsed)


def build(case: dict[str, Any], facts: dict[str, Any]) -> EvaluationState:
    scope = case["scope"]
    now = datetime.fromisoformat(scope["now"])
    period = Period(tuple(scope["accounts"]), datetime.fromisoformat(scope["start"]),
                    datetime.fromisoformat(scope["end"]))
    rows = ledger_rows(facts["rows"])
    batches = [AccountBatch(a, period.start, period.end,
                           datetime.fromisoformat(facts["account_as_of"][a]),
                           tuple(r for r in rows if r.account_id == a))
               for a in period.accounts if a not in facts["omit_accounts"]]
    originals = [AccountBatch(b["account_id"], datetime.fromisoformat(b["start"]),
                             datetime.fromisoformat(b["end"]), datetime.fromisoformat(b["as_of"]),
                             ledger_rows(b["rows"])) for b in facts["original_batches"]]
    return EvaluationState(assemble(period, batches, now=now, original_batches=originals), now)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_arithmetic_golden(case: dict[str, Any]) -> None:
    expected = case["expected"]
    assert expected, "an empty expected result is not an evaluation"
    if "error" in expected:
        assert set(expected) == {"error"}
        with pytest.raises(FactsError, match="^" + re.escape(expected["error"]) + "$"):
            build(case, case["facts"])
        return
    state = build(case, case["facts"])
    s = state.snapshot
    t = totals(s)
    actual = {key: getattr(t, key) for key in (
        "gross", "refund", "net", "record_count", "transfer_out", "transfer_in")}
    actual.update({
        "monthly_average": monthly_average(s, now=state.now),
        "statistical_days": statistical_days(s, now=state.now),
        "category_net": {c.category: c.net for c in t.categories},
        "share_bps": {c.category: c.share_bps for c in t.categories},
        "rank": {c.category: i for i, c in enumerate(t.categories, 1)},
        "ratios_null": all(c.share is None for c in t.categories),
        "as_of": s.as_of.isoformat(),
    })
    if "comparison" in expected or "change_bps" in expected:
        assert case["reference"] is not None
        d = compare(s, build(case, case["reference"]).snapshot)
        actual["comparison"] = {"reference_net": d.reference_net, "delta": d.delta,
                                "change": str(d.change) if d.change is not None else None,
                                "largest_change_category": d.largest_change_category}
        actual["change_bps"] = d.change_bps
    if "details" in expected:
        actual["details"] = {category: [r.transaction_id for r in select_rows(s, category)]
                             for category in expected["details"]}
    assert set(expected) <= set(actual), "unknown assertion field must not be silently ignored"
    for key, value in expected.items():
        if isinstance(value, dict):
            for field, target in value.items():
                assert actual[key][field] == target, (case["id"], key, field)
        else:
            assert actual[key] == value, (case["id"], key)
