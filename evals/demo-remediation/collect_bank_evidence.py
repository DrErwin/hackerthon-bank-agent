"""Read-only, allowlisted evidence from an isolated synthetic demo database."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3


def rows(path, query, args=()):
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, args)]


def collect(directory, task_ids):
    application = directory / "application.sqlite3"
    bank = directory / "mock_bank.sqlite3"
    tasks = []
    for task_id in task_ids:
        record, = rows(application, "SELECT task_id,status,revision,snapshot_json FROM tasks WHERE task_id=?", (task_id,))
        snapshot = json.loads(record.pop("snapshot_json"))
        result = snapshot.get("result", {})
        data = result.get("data") or {}
        record.update(capability=snapshot.get("capability_name"),
                      scope=snapshot.get("completed_bill_scope"),
                      source_task_id=snapshot.get("bill_source_task_id"),
                      operation_id=data.get("operation_id"),
                      amount_fen=data.get("amount_fen"),
                      transaction_id=(data.get("operation") or {}).get("receipt", {}).get("transaction_id"))
        tasks.append(record)
    operations = rows(bank, "SELECT operation_id,action_name,status FROM bank_operations WHERE operation_id NOT LIKE 'seed:%' ORDER BY recorded_at")
    ledger = rows(bank, "SELECT transaction_id,operation_id,amount_fen,direction FROM ledger_entries WHERE operation_id NOT LIKE 'seed:%' ORDER BY occurred_at")
    cancelled = rows(bank, "SELECT mandate_id,status,cancel_operation_id FROM bank_subscriptions WHERE cancel_operation_id IS NOT NULL")
    return {"captured_at": datetime.now(timezone.utc).isoformat(),
            "layer": "read-only-isolated-mock-bank-not-real-bank", "tasks": tasks,
            "operations": operations, "ledger": ledger, "cancelled_subscriptions": cancelled}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-directory", type=Path, required=True)
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("preserve existing evidence; choose a new output")
    result = collect(args.data_directory, args.task)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
