"""v05-platform/01 (Issue #121) F35 + F24 audit end-to-end evidence.

Repeatable: run with the project venv; it builds the real API app, real audit journal
and mock bank, replacing only the model with the scripted test planner.

    python .scratch/v05-platform/evidence/2026-10-21/run_f35_evidence.py

Artifacts written next to this script:
    audit-export-round.json   the frozen whole-round JSON evidence package
    audit-export-task.json    the frozen task-scoped package
    summary.json              hashes, counts and every check performed
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.api.test_app import admin_login, finish_transfer, make_app, post  # noqa: E402

HERE = Path(__file__).resolve().parent


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def package_hashes_hold(package: dict) -> int:
    for item in package["evidence"].values():
        encoded = json.dumps(item["content"], ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"))
        assert hashlib.sha256(encoded.encode()).hexdigest() == item["snapshot"]["content_hash"]
    return len(package["evidence"])


def main() -> int:
    checks: dict[str, object] = {}
    summary: dict[str, object] = {"ticket": "v05-platform/01", "source_issue": 121,
                                  "checks": checks}
    with TemporaryDirectory() as tmp:
        path = Path(tmp)
        user_app, admin_app = make_app(path), make_app(path)
        with TestClient(user_app) as user, TestClient(admin_app) as admin:
            task_id, code = finish_transfer(user)
            admin_login(admin)

            created = post(admin, "/admin/audit/exports", demo_round_id="D1")
            assert created.status_code == 200, created.text
            view = created.json()["data"]
            checks["export_view"] = {key: view[key] for key in
                                     ("kind", "status", "task_id", "file_name", "media_type")}

            first = admin.get(f"/api/v1/exports/{view['export_id']}/download")
            assert first.status_code == 200, first.text
            (HERE / "audit-export-round.json").write_bytes(first.content)
            package = first.json()
            checks["round_package"] = {
                "bytes": len(first.content),
                "sha256": digest(first.content),
                "event_count": package["summary"]["event_count"],
                "evidence_count": package_hashes_hold(package),
                "missing_count": len(package["missing"]),
                "event_types": sorted({event["event_type"] for event in package["events"]}),
                "self_export_event": [
                    event["payload"]["export_id"] for event in package["events"]
                    if event["event_type"] == "audit.accessed"
                    and event["payload"]["action"] == "export"],
            }
            checks["verification_code_absent"] = code not in first.text

            # New access events must not move the frozen file.
            assert admin.get("/api/v1/admin/audit/events",
                             params={"task_id": task_id}).status_code == 200
            second = admin.get(f"/api/v1/exports/{view['export_id']}/download")
            assert second.status_code == 200
            checks["frozen_after_new_events"] = second.content == first.content
            checks["frozen_sha_after_new_events"] = (
                digest(second.content) == checks["round_package"]["sha256"])

            scoped = post(admin, "/admin/audit/exports", demo_round_id="D1", task_id=task_id)
            assert scoped.status_code == 200, scoped.text
            scoped_view = scoped.json()["data"]
            scoped_file = admin.get(f"/api/v1/exports/{scoped_view['export_id']}/download")
            assert scoped_file.status_code == 200, scoped_file.text
            (HERE / "audit-export-task.json").write_bytes(scoped_file.content)
            scoped_package = scoped_file.json()
            checks["task_package"] = {
                "bytes": len(scoped_file.content),
                "sha256": digest(scoped_file.content),
                "task_id": scoped_package["task_id"],
                "event_count": scoped_package["summary"]["event_count"],
                "all_events_scoped": {event["task_id"] for event in scoped_package["events"]} == {task_id},
            }
            checks["audit_trail"] = {
                "export": [event.payload.export_id for event
                           in admin_app.state.api.runtime.audit._events("D1")
                           if event.event_type == "audit.accessed"
                           and event.payload.action == "export"],
                "download": [event.payload.export_id for event
                             in admin_app.state.api.runtime.audit._events("D1")
                             if event.event_type == "audit.accessed"
                             and event.payload.action == "download"],
            }
            checks["model_calls"] = {
                "user": user_app.state.api.runtime.harness.planner.calls,
                "admin": admin_app.state.api.runtime.harness.planner.calls,
            }
    (HERE / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    required = (
        checks["verification_code_absent"],
        checks["frozen_after_new_events"],
        checks["frozen_sha_after_new_events"],
        checks["task_package"]["all_events_scoped"],
        checks["model_calls"] == {"user": 1, "admin": 0},
        checks["round_package"]["self_export_event"] == [view["export_id"]],
        checks["audit_trail"]["export"] == [view["export_id"], scoped_view["export_id"]],
        checks["audit_trail"]["download"] == [view["export_id"], view["export_id"],
                                              scoped_view["export_id"]],
    )
    return 0 if all(required) else 1


if __name__ == "__main__":
    raise SystemExit(main())
