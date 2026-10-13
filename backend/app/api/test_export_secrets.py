"""交付包验收标准 2：报告与导出链路（F21—F24）不泄漏验证码，并保持银行口径的打码。

F22 明细导出是 v0.4 最敏感的公共链路：先完成本次验证，再惰性生成 CSV。
本用例把整条链路跑一遍，然后扫描每一件对外产物与平台库的每一张用户表，
确认验证码只存在于受控的演示提示通道（F19 demo-code，no-store）与银行侧
（银行要校验它，属既定事实），绝不进入应用的响应、事件或持久层；CSV 也
只保留银行侧给出的打码形态。
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
        return [(name, list(connection.execute(f'SELECT * FROM "{name}"'))) for name in names]
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

        # 1) 对外产物：创建 / 验证与状态回执、任务视图、验证历史回放、F21 卡片、
        #    明细 CSV、该线程前 100 条 SSE 事件；正文与响应头一起扫描（头也可能回显）。
        #    审计视图的等价证据由下方 audit_events 表扫描覆盖。
        views = {
            "status": client.get(f"/api/v1/exports/{export['export_id']}"),
            "task": client.get(f"/api/v1/tasks/{export['task_id']}"),
            "records": client.get(f"/api/v1/tasks/{export['task_id']}/records"),
            "card": client.get(f"/api/v1/reports/{report.report_id}"),
        }
        for name, response in views.items():
            # 错误信封同样"非空且无命中"：先确认拿到的是正常产物再扫描。
            assert response.status_code == 200, f"{name}: {response.status_code}"
        events = service.store.events(task["thread_id"], None)
        assert events, "该线程的事件产物不得为空，否则空列表会让扫描静默通过"
        artifacts = {
            "create": (created.text, str(dict(created.headers))),
            "verify": (done.text, str(dict(done.headers))),
            "download": (download.text, str(dict(download.headers))),
            "events": (str(events),),
            **{name: (response.text, str(dict(response.headers))) for name, response in views.items()},
        }
        for name, cells in artifacts.items():
            assert stored_code_leak([cells], code) is None, name

        # 2) 平台库（application.sqlite）的全部用户表，含导出链路写的三张。
        #    先确认覆盖面与行数——枚举为空或路径写错时下面的循环一次都不会执行，
        #    空表扫描也会静默通过。
        tables = dict(platform_rows(service.runtime.application.path))
        assert {"api_exports", "api_reports", "api_tasks"} <= set(tables), \
            "导出链路写入的表必须在扫描范围内"
        assert all(tables[name] for name in ("api_exports", "api_reports", "api_tasks")), \
            "本次链路必须真的写入这些行，否则扫描在空表上静默通过"
        for table, rows in tables.items():
            leak = stored_code_leak(rows, code)
            assert leak is None, f"{table}: {leak!r}"

        # 3) 明细导出按银行事实出账：商户名原样、账号保持银行侧给出的打码形态。
        #    夹具里没有未打码账号（也不该造），本断言证明口径透传，不证明打码逻辑。
        assert "楼下面馆" in download.text
        assert "6222****1234" in download.text
