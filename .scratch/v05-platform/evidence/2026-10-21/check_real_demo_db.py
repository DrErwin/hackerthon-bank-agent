"""Real-demo-database acceptance for the export-table migration and F35 round export.

Two checks, both repeatable with the project venv:

    python .scratch/v05-platform/evidence/2026-10-21/check_real_demo_db.py

1. synthetic: a pre-F35 `api_exports` table (report_id/thread_id NOT NULL) keeps its rows
   after `ApiStore` migrates it, and an audit export row can then be stored without a
   report or thread.
2. real data: a copy of `.mnemon/v03-local-demo` (never the original) is opened through
   the real API app; F35 round export runs over that round's real audit history and the
   downloaded JSON package is measured (size, hash, event count, wall time).

Writes real-demo-check.json next to this script.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.store import ApiStore  # noqa: E402
from app.api.test_app import admin_login, make_app, post  # noqa: E402

HERE = Path(__file__).resolve().parent
# Pass the demo data directory as the first argument when the repository's
# local-demo databases live outside this checkout (e.g. a worktree).
DEMO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("LOCAL_DEMO_DATA_DIR", ROOT / ".mnemon" / "v03-local-demo"))
OLD_EXPORTS = """CREATE TABLE api_exports (
    export_id TEXT PRIMARY KEY, report_id TEXT NOT NULL, kind TEXT NOT NULL,
    user_id TEXT NOT NULL, demo_round_id TEXT NOT NULL,
    session_id TEXT NOT NULL, task_id TEXT, challenge_id TEXT,
    thread_id TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
    file_name TEXT, media_type TEXT, content TEXT,
    error_code TEXT, error_reason TEXT)"""


def columns(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        return {row[1]: row[3] for row in connection.execute("PRAGMA table_info(api_exports)")}
    finally:
        connection.close()


def counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(path)
    try:
        return {
            "exports": connection.execute("SELECT COUNT(*) FROM api_exports").fetchone()[0],
            "events": connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
        }
    finally:
        connection.close()


def export_rows(path: Path) -> int:
    connection = sqlite3.connect(path)
    try:
        return connection.execute("SELECT COUNT(*) FROM api_exports").fetchone()[0]
    finally:
        connection.close()


def synthetic_preservation() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "application.sqlite3"
        connection = sqlite3.connect(path)
        connection.execute(OLD_EXPORTS)
        connection.execute(
            "INSERT INTO api_exports VALUES ('E1','R1','card','U1','D1','S1',NULL,NULL,"
            "'T1','ready','2026-10-21T00:00:00+00:00','f.html','text/html','old',NULL,NULL)")
        connection.commit()
        connection.close()
        before = columns(path)
        store = ApiStore(path, b"s" * 32)
        store.save_export({"export_id": "E2", "report_id": None, "kind": "audit",
                           "user_id": "demo-admin", "demo_round_id": "D1",
                           "session_id": "S2", "task_id": None, "challenge_id": None,
                           "thread_id": None, "status": "ready",
                           "created_at": "2026-10-21T00:00:01+00:00"})
        after = columns(path)
        preserved = store.export_row("E1", "U1", "D1")
        audit = store.export_row("E2", "demo-admin", "D1")
        return {
            "old_report_id_notnull": before["report_id"] == 1,
            "new_report_id_nullable": after["report_id"] == 0,
            "new_thread_id_nullable": after["thread_id"] == 0,
            "preserved_rows": export_rows(path),
            "preserved_content": preserved["content"] if preserved else None,
            "audit_row": {key: audit[key] for key in
                          ("kind", "report_id", "thread_id", "status")} if audit else None,
        }


def real_demo() -> dict:
    if not (DEMO / "application.sqlite3").exists():
        return {"skipped": "no local demo database"}
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        shutil.copy2(DEMO / "application.sqlite3", target / "application.sqlite")
        shutil.copy2(DEMO / "mock_bank.sqlite3", target / "bank.sqlite")
        before_schema = columns(target / "application.sqlite")
        before_counts = counts(target / "application.sqlite")
        app = make_app(target)
        with TestClient(app) as admin:
            admin_login(admin)
            started = time.perf_counter()
            created = post(admin, "/admin/audit/exports", demo_round_id="D1")
            elapsed = time.perf_counter() - started
            assert created.status_code == 200, created.text
            view = created.json()["data"]
            started = time.perf_counter()
            download = admin.get(f"/api/v1/exports/{view['export_id']}/download")
            download_elapsed = time.perf_counter() - started
            assert download.status_code == 200, download.text
            package = download.json()
        after_schema = columns(target / "application.sqlite")
        round_events = package["summary"]["event_count"]
        return {
            "old_report_id_notnull": before_schema["report_id"] == 1,
            "new_report_id_nullable": after_schema["report_id"] == 0,
            "round_events_before_export": before_counts["events"],
            "export_rows_before": before_counts["exports"],
            "export_view": {key: view[key] for key in
                            ("kind", "status", "task_id", "media_type")},
            "package_bytes": len(download.content),
            "package_sha256": hashlib.sha256(download.content).hexdigest(),
            "package_event_count": round_events,
            "package_evidence_count": len(package["evidence"]),
            "package_missing_count": len(package["missing"]),
            "events_match_journal": round_events == before_counts["events"] + 1,
            "create_seconds": round(elapsed, 3),
            "download_seconds": round(download_elapsed, 3),
        }


def main() -> int:
    result = {"ticket": "v05-platform/01",
              "synthetic_migration": synthetic_preservation(),
              "real_demo": real_demo()}
    (HERE / "real-demo-check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    synthetic = result["synthetic_migration"]
    ok = (synthetic["old_report_id_notnull"] and synthetic["new_report_id_nullable"]
          and synthetic["new_thread_id_nullable"] and synthetic["preserved_rows"] == 2
          and synthetic["audit_row"] == {"kind": "audit", "report_id": None,
                                        "thread_id": None, "status": "ready"})
    real = result["real_demo"]
    if "skipped" not in real:
        ok = ok and real["new_report_id_nullable"] and real["events_match_journal"]
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
