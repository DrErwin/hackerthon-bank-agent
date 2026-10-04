"""Real built React + TCP API, with browser-owned response ordering faults."""

from dataclasses import replace
import hashlib
from pathlib import Path
import socket
import threading
import time

from fastapi.staticfiles import StaticFiles
import uvicorn

from scenarios import expire_session


def run_browser(e, n, dist, evidence_directory):
    from playwright.sync_api import sync_playwright, expect
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    e.service.config = replace(e.service.config, origins=("http://testserver", url))
    e.api.mount("/", StaticFiles(directory=dist, html=True), name="evaluation-react")
    server = uvicorn.Server(uvicorn.Config(e.api, log_level="error", access_log=False))
    worker = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    worker.start()
    try:
        deadline = time.monotonic() + 5
        while not server.started and time.monotonic() < deadline: time.sleep(.02)
        if not server.started: raise RuntimeError("REACT_HTTP_SERVER_NOT_READY")
        if n == 7:
            e.plan.hint, e.plan.amount = "张伟", 10_000
            e.plan.text = "给张伟转100元，使用默认主账户A1。"
            e.allow("A1", "A9", 10_000)
        e.start()
        if not e.task:
            e.check("browser.task_precondition", False); return
        original_task = e.task["task_id"]
        original_interaction = e.task["interaction"]["interaction_id"]
        e.zero()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1400, "height": 1000})
            context.add_cookies([{"name": "bank_session", "value": e.session, "domain": "127.0.0.1", "path": "/api/v1", "httpOnly": True, "sameSite": "Lax"}])
            page = context.new_page()
            requests, held, connections = [], [], []
            page.on("request", lambda request: requests.append({"method": request.method, "path": request.url.split(url)[-1].split("?")[0]}))

            def events(route):
                connections.append(route.request.url)
                if n == 6 or n == 3 and len(connections) == 1: route.abort()
                else: route.continue_()

            if n in (3, 6): page.route("**/api/v1/threads/*/events", events)
            if n in (4, 5, 7):
                def snapshots(route):
                    response = route.fetch()
                    if not held: held.append((route, response))
                    else: route.fulfill(response=response)
                page.route("**/api/v1/tasks?**", snapshots)
            page.goto(url, wait_until="domcontentloaded")
            if n in (4, 5, 7):
                deadline = time.monotonic() + 10
                while not held and time.monotonic() < deadline: page.wait_for_timeout(50)
                e.check("browser.old_snapshot_captured", bool(held))
                if not held: return
            if n == 3:
                expect(page.get_by_role("button", name="确认办理", exact=True)).to_be_visible(timeout=15_000)
                expect(page.locator(".connection-label")).to_contain_text("连接", timeout=15_000)
                page.wait_for_timeout(3500)
                e.check("browser.SSE_reconnected", len(connections) >= 2, len(connections))
                page.get_by_role("button", name="刷新任务状态", exact=True).click()
                e.get_task()
                e.check("browser.same_task", e.task["task_id"] == original_task)
                e.check("browser.no_message_replay", not any(r["method"] == "POST" and r["path"].endswith("/messages") for r in requests))
                e.zero()
            elif n == 4:
                page.wait_for_timeout(200)
                e.complete(); e.success()
                expect(page.locator(".task-card")).to_contain_text("成功", timeout=15_000)
                held[0][0].fulfill(response=held[0][1])
                page.wait_for_timeout(200)
                expect(page.locator(".task-card")).to_contain_text("成功")
                e.check("browser.old_confirmation_not_revived", page.get_by_role("button", name="确认办理", exact=True).count() == 0)
            elif n == 5:
                page.get_by_role("button", name="＋ 新对话", exact=True).click()
                page.wait_for_timeout(200)
                held[0][0].fulfill(response=held[0][1])
                page.wait_for_timeout(200)
                e.check("browser.foreign_thread_card_absent", page.locator(".task-card").count() == 0)
                e.zero()
            elif n == 6:
                expect(page.get_by_role("button", name="确认办理", exact=True)).to_be_visible(timeout=15_000)
                expire_session(e)
                page.get_by_role("button", name="确认办理", exact=True).click()
                expect(page.get_by_role("button", name="重新进入", exact=True)).to_be_visible(timeout=15_000)
                e.check("browser.401_disables_old_controls", page.get_by_role("button", name="确认办理", exact=True).count() == 0)
                e.zero()
            elif n == 7:
                e.input(selected_option_id="A9")
                expect(page.get_by_role("button", name="确认办理", exact=True)).to_be_visible(timeout=15_000)
                held[0][0].fulfill(response=held[0][1])
                page.wait_for_timeout(200)
                e.check("browser.current_target_retained", "2222" in page.locator(".task-card").inner_text())
                e.check("browser.old_candidates_not_revived", page.locator(".candidate-button").count() == 0)
                r = e.post(f"/tasks/{original_task}/inputs", interaction_id=original_interaction, selected_option_id="A8")
                e.check("browser.stale_selection_rejected", r.status_code == 409)
                e.get_task(); e.check("browser.payee_still_A9", e.task["data"]["payee"]["payee_id"] == "A9"); e.zero()
            storage = page.evaluate("JSON.stringify({local: {...localStorage}, session: {...sessionStorage}})")
            e.check("browser.storage_no_secrets", all(secret not in storage for secret in e.secrets))
            evidence_directory.mkdir(parents=True, exist_ok=True)
            picture = evidence_directory / (e.case["id"] + ".png")
            page.screenshot(path=str(picture), full_page=True)
            e.browser_evidence = {"status": "Passed", "transport": "TCP HTTP + built React, real-api",
                "screenshot": str(picture), "screenshot_sha256": hashlib.sha256(picture.read_bytes()).hexdigest(),
                "dom": page.locator("body").inner_text(), "requests": requests,
                "frontend_build": hashlib.sha256((dist / "index.html").read_bytes()).hexdigest()}
            context.close(); browser.close()
    finally:
        server.should_exit = True
        worker.join(timeout=5)
        sock.close()
