"""交付包验收标准 2：报告与导出链路（F21—F24）不泄漏验证码或未打码账号。

F22 明细导出是 v0.4 最敏感的公共链路：先完成本次验证，再惰性生成 CSV。
本用例把整条链路跑一遍，然后扫描每一件对外产物与平台库的每一张用户表，
确认验证码只存在于受控的演示提示通道（F19 demo-code，no-store）与银行侧
（银行要校验它，属既定事实），绝不进入应用的响应、事件或持久层。
"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.test_app import _bill_report, _seed_details_row, make_app, post, start
from app.api.test_verification_fault import stored_code_leak
from app.storage.database import connect


def platform_rows(path):
    """Every user table of the platform database, so a new table is covered by default."""

    connection = connect(path)
    try:
        names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return [(name, list(connection.execute(f"SELECT * FROM {name}"))) for name in names]
    finally:
        connection.close()


def test_details_export_never_stores_or_returns_the_verification_code(tmp_path):
    app = make_app(tmp_path)
    _seed_details_row(tmp_path)
    with TestClient(app) as client:
        _, task = start(client)
        service = app.state.api
        owner = service.identity(client.cookies.get("bank_session"))
        report = service.capture_report(owner, task["task_id"], _bill_report())

        created = post(client, f"/reports/{report.report_id}/exports", kind="details")
        assert created.status_code == 200, created.text
        export = created.json()["data"]
        waiting = client.get(f"/api/v1/tasks/{export['task_id']}").json()["data"]
        challenge = waiting["interaction"]["record_ref"]

        # 验证码只从受控演示通道取，且该响应不得被缓存。
        demo = client.get(f"/api/v1/verifications/{challenge}/demo-code")
        assert demo.status_code == 200, demo.text
        assert demo.headers["cache-control"] == "no-store"
        code = demo.json()["data"]["code"]

        done = post(client, f"/verifications/{challenge}/code",
                    submission_id=str(uuid4()), code=code)
        assert done.status_code == 200, done.text
        assert done.json()["data"]["kind"] == "verified"
        download = client.get(f"/api/v1/exports/{export['export_id']}/download")
        assert download.status_code == 200, download.text

        # 1) 对外产物：创建 / 验证与状态回执、任务视图、F21 卡片、CSV、SSE 事件。
        artifacts = {
            "create": created.text,
            "verify": done.text,
            "status": client.get(f"/api/v1/exports/{export['export_id']}").text,
            "task": client.get(f"/api/v1/tasks/{export['task_id']}").text,
            "card": client.get(f"/api/v1/reports/{report.report_id}").text,
            "csv": download.text,
            "events": str(service.store.events(task["thread_id"], None)),
        }
        for name, artifact in artifacts.items():
            assert stored_code_leak([(artifact,)], code) is None, name

        # 2) 平台持久层：全部用户表（含导出链路写的 api_exports / api_reports / api_tasks）。
        for table, rows in platform_rows(service.runtime.application.path):
            leak = stored_code_leak(rows, code)
            assert leak is None, f"{table}: {leak!r}"

        # 3) 明细导出仍按银行事实出账：商户名不额外打码，账号保持银行侧打码。
        assert "楼下面馆" in download.text
        assert "6222****1234" in download.text
