"""Shared demo flow facts: JSON rows with month offsets, resolved at the bank clock."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime
import json
from pathlib import Path

SEEDS_DIR = Path(__file__).parent / "seeds"
FLOW_SEED_FILE = "flow_history.json"


def _occurred_at(at: datetime, month_offset: int, day: int, time_text: str) -> datetime | None:
    """Resolve one seed row onto the bank clock; the current month keeps only past days."""
    month_index = at.month - 1 - month_offset
    year = at.year + month_index // 12
    month = month_index % 12 + 1
    if day > monthrange(year, month)[1] or (month_offset == 0 and day > at.day):
        return None
    hour, minute = (int(part) for part in time_text.split(":"))
    return at.replace(year=year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)


def build_flow_rows(at: datetime, *, seeds_dir: Path = SEEDS_DIR) -> list[dict]:
    """Turn the relative seed file into fully-formed ledger facts for ``at``.

    Seeded transfers never land on the bank's current day: they would silently eat
    the demo's daily transfer limit (``get_limits`` counts them like any transfer).
    """
    seeds = json.loads((seeds_dir / FLOW_SEED_FILE).read_text(encoding="utf-8"))
    resolved: dict[str, tuple[str, datetime]] = {}
    for seed in seeds:
        occurred_at = _occurred_at(at, seed["month_offset"], seed["day"], seed["time"])
        if occurred_at is None:
            continue
        if seed["nature"] == "transfer" and occurred_at.date() == at.date():
            continue
        resolved[seed["ref"]] = (
            f"SEED-{seed['account_id']}-{occurred_at:%Y%m%d}-{seed['ref']}", occurred_at,
        )
    rows = []
    for seed in seeds:
        entry = resolved.get(seed["ref"])
        if entry is None:
            continue
        transaction_id, occurred_at = entry
        original_transaction_id = original_occurred_at = None
        if seed.get("original_ref") is not None:
            original = resolved.get(seed["original_ref"])
            if original is None:
                raise ValueError(f"flow seed {seed['ref']} references a missing original row")
            original_transaction_id, original_occurred_at = original[0], original[1].isoformat()
        rows.append({
            "transaction_id": transaction_id,
            "account_id": seed["account_id"], "user_id": seed["user_id"],
            "amount_fen": seed["amount_fen"], "direction": seed["direction"],
            "nature": seed["nature"], "category": seed["category"],
            "occurred_at": occurred_at.isoformat(),
            "counterparty_id": seed.get("counterparty_id"),
            "counterparty_name": seed["counterparty_name"],
            "counterparty_account_masked": seed.get("counterparty_account_masked"),
            "channel": seed.get("channel"), "summary": seed["summary"],
            "original_transaction_id": original_transaction_id,
            "original_occurred_at": original_occurred_at,
        })
    return rows
