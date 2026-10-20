"""Security React evidence: the built frontend served by the real API, browser-driven.

Offline fixed planner only. This batch proves confirmation display, button
state and the no-approval chat behaviour in the real React UI; model-layer
interpretation stays with the live runs (case doc section 4.4).
"""

import gzip
import hashlib
import json
import socket
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

SECURITY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SECURITY_DIR))

from security_runner import (  # noqa: E402
    ROOT, _environment, _output_inside_repository, load_security_catalog, select_cases,
)

DIST = ROOT / "frontend" / "dist"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _start_server(env, url: str):
    import uvicorn
    from fastapi.staticfiles import StaticFiles

    env.service.config = replace(env.service.config, origins=("http://testserver", url))
    env.api.mount("/", StaticFiles(directory=DIST, html=True), name="security-react-evidence")
    server = uvicorn.Server(uvicorn.Config(env.api, log_level="error", access_log=False))
    return server


def _run_browser(env, url: str, scenario: dict) -> dict:
    from playwright.sync_api import expect, sync_playwright

    captured = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 1000})
        context.add_cookies([{
            "name": "bank_session", "value": env.session, "domain": "127.0.0.1",
            "path": "/api/v1", "httpOnly": True, "sameSite": "Lax",
        }])
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        # v0.4 ticket 05: the complete shell is the root entry; wait for its composer.
        page.wait_for_function(
            "() => document.querySelector('#sh-input') && !document.querySelector('#sh-input').disabled",
            timeout=30_000)
        confirm_button = page.get_by_role("button", name="确认办理", exact=True)
        # A pre-existing waiting task is shown behind the shell recovery gate.
        try:
            expect(confirm_button).to_be_visible(timeout=8_000)
        except AssertionError:
            page.get_by_role("button", name="查看原任务", exact=True).click()
            expect(confirm_button).to_be_visible(timeout=20_000)
        card = page.locator(".sh-task")
        card_text = card.inner_text()
        env.check("react.confirmation_card_amount", "500.00" in card_text, card_text)
        env.check("react.confirmation_note_present",
                  "不算数" in card_text and "确认" in card_text, card_text)
        pending = env.confirmation()
        env.check("react.backend_decision_pending",
                  pending is not None and pending["decision"] == "pending",
                  pending["decision"] if pending else "no_confirmation")

        if scenario["followup_text"]:
            env.planner.plan.variant = "INP-18"
            page.locator("#sh-input").fill(scenario["followup_text"])
            page.get_by_role("button", name="发送", exact=True).click()
            page.wait_for_timeout(3_000)
            env.get_task()
            pending_after = env.confirmation()
            env.check("react.followup_keeps_pending",
                      pending_after is not None and pending_after["decision"] == "pending",
                      pending_after["decision"] if pending_after else "no_confirmation")
            env.check("react.followup_button_still_active",
                      confirm_button.count() == 1 and confirm_button.is_enabled())
            card_after = card.inner_text()
            env.check("react.followup_no_success", "成功" not in card_after, card_after)
            env.check("react.followup_single_task", page.locator(".sh-task").count() == 1)
            env.zero()
            captured["dom_after_followup"] = page.locator("body").inner_text()
        else:
            confirm_button.click()
            code_input = page.get_by_label("请输入 6 位验证码")
            expect(code_input).to_be_visible(timeout=20_000)
            page.get_by_role("button", name="点这里查看", exact=True).click()
            panel = page.locator(".sh-demo-code strong")
            expect(panel).to_be_visible(timeout=15_000)
            code = panel.inner_text().strip()
            env.secrets.append(code)
            code_input.fill(code)
            page.get_by_role("button", name="提交验证码", exact=True).click()
            expect(card).to_contain_text("成功", timeout=25_000)
            env.get_task()
            env.success()
            env.check("react.success_amount_shown", "500.00" in card.inner_text(), card.inner_text())
            captured["dom_after_success"] = page.locator("body").inner_text()

        storage = page.evaluate("JSON.stringify({local: {...localStorage}, session: {...sessionStorage}})")
        env.check("react.storage_no_secrets", all(secret not in storage for secret in env.secrets))
        shot = Path(scenario["screenshot"])
        shot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shot), full_page=True)
        context.close()
        browser.close()
    return captured


def run_scenario(case: dict, work: Path, followup_text: str | None, screenshot: Path) -> dict:
    env = _environment(work, case)
    try:
        env.start()
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        server = _start_server(env, url)
        worker = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started and time.monotonic() < deadline:
                time.sleep(0.02)
            if not server.started:
                raise RuntimeError("REACT_HTTP_SERVER_NOT_READY")
            scenario = {"followup_text": followup_text, "screenshot": str(screenshot)}
            captured = _run_browser(env, url, scenario)
            checks = [dict(item) for item in env.assertions]
            return {
                "case_id": case["id"],
                "checks": checks,
                "status": "Passed" if all(item["passed"] for item in checks) else "Failed",
                "captured": captured,
            }
        finally:
            server.should_exit = True
            sock.close()
    finally:
        env.close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Security React evidence (offline planner)")
    parser.add_argument("--output", required=True)
    parser.add_argument("--date", default="2026-10-10",
                        help="evidence date directory, e.g. 2026-10-21")
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    if _output_inside_repository(output):
        raise ValueError("INSIDE_REPOSITORY")

    catalog = load_security_catalog()
    c001 = select_cases(catalog, ["SEC-C-001"])[0]
    p002 = select_cases(catalog, ["SEC-P-002"])[0]

    browser_dir = SECURITY_DIR / "evidence" / args.date / "react-browser"
    report = {
        "schema_version": "security-react-evidence-v1",
        "date": args.date,
        "transport": "TCP HTTP + built React dist + real FastAPI service, offline fixed planner",
        "frontend_build_sha256": _sha256(DIST / "index.html"),
        "browser": "playwright chromium headless",
        "scenarios": [],
        "notes": "本批只证明真实React确认展示、按钮状态与聊天不批准；模型层解释按正文4.4由live运行与人工复核判定。",
    }
    import tempfile

    with tempfile.TemporaryDirectory(prefix="security-react-") as work:
        base = Path(work)
        # The browser writes screenshots directly; capture them under the work
        # directory first, then archive copies next to the report.
        shot_c001 = base / "SEC-C-001.png"
        shot_p002 = base / "SEC-P-002.png"
        report["scenarios"].append(
            run_scenario(c001, base / "c001", followup_text="嗯", screenshot=shot_c001))
        report["scenarios"].append(
            run_scenario(p002, base / "p002", followup_text=None, screenshot=shot_p002))

        browser_dir.mkdir(parents=True, exist_ok=True)
        for shot in (shot_c001, shot_p002):
            target = browser_dir / shot.name
            if target.exists():
                raise FileExistsError(target)
            target.write_bytes(shot.read_bytes())
        for scenario in report["scenarios"]:
            shot = browser_dir / (scenario["case_id"] + ".png")
            scenario["screenshot"] = str(shot.relative_to(SECURITY_DIR))
            scenario["screenshot_sha256"] = _sha256(shot)

    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "scenarios": [(s["case_id"], s["status"]) for s in report["scenarios"]],
    }, ensure_ascii=False))
    return 0 if all(s["status"] == "Passed" for s in report["scenarios"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
