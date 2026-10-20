"""Run every sample and report observed failures, blockers and separate redlines."""

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import hashlib
import subprocess
import time
import traceback

from app.audit.journal import redact

from catalog import STANDARD_IDS, data_version, load_cases
from environment import Environment, InputUnavailable
from plans import plan_for
from scenarios import common_checks, execute


def run_case(case, directory, delegate=None, live_blocker=None, react_dist=None, evidence_directory=None):
    plan = plan_for(case)
    started = time.monotonic()
    result = {"id": case["id"], "scenario_id": case["scenario_id"], "standard": case["standard"],
              "layer": "live-glm" if delegate or live_blocker else "offline-real-services",
              "status": "NotRun", "provider": None, "steps": [], "assertions": [],
              "model_interactions": [], "submissions": [], "bank_reads": [],
              "react": {"status": "Blocked", "provider": "frontend/", "reason": "尚无本轮真实React证据"},
              "security_professional": {"status": "NotRun", "provider": "Ringo"}}
    result["substitutes"] = ["per-action risk facts", "controlled wall-clock and bank calendar", "named storage/transport/audit faults where required"]
    if not delegate: result["substitutes"].append("fixed proposal")
    if plan.variant == "INP-17": result["substitutes"].append("injected provider timeout; no live request for this sample")
    browser_case = plan.variant in ("OBS-03", "OBS-04", "OBS-05", "OBS-06", "OBS-07")
    if browser_case and react_dist:
        if plan.variant == "OBS-05":
            # The v0.4 complete shell is a single-conversation entry; it has no
            # thread switch action, so a delayed response for another thread cannot
            # be exercised through the new UI. The equivalent guard is covered by
            # frontend/src/ui-recovery.test.tsx.
            plan.blocked = ("v0.4完整前端为单会话入口，无对话切换动作，本场景在新入口不适用；"
                            "等价保护由 frontend/src/ui-recovery.test.tsx（迟到历史不进入当前对话）覆盖；"
                            "旧前端证据见 evals/transfer/evidence/2026-10-11")
        else:
            plan.blocked = None
    if live_blocker or plan.blocked:
        result.update(status="Blocked", provider="GLM配置/供应商" if live_blocker else "Ringo" if "Ringo" in plan.blocked else "frontend/",
                      reason=live_blocker or plan.blocked)
    else:
        env = None
        try:
            env = Environment(directory, case, plan, delegate)
            if browser_case:
                from browser_checks import run_browser
                run_browser(env, int(plan.variant[-2:]), react_dist, evidence_directory or directory / "browser")
            else:
                try:
                    execute(env)
                except InputUnavailable:
                    # Keep the failed business assertions and still check funds/privacy.
                    env.get_task()
                    env.snapshot("final")
            common_checks(env)
            failed = [v["name"] for v in env.assertions if not v["passed"]]
            result.update(status="Failed" if failed else "Passed", failed_assertions=failed)
            if failed: result["provider"] = "产品归属目录；见失败断言与实际步骤"
            if delegate and plan.variant != "INP-17" and any(v.get("error_type") for v in env.planner.records):
                result.update(status="Blocked", provider="模型规划/接入（归因未确定）", reason="模型调用未返回可用规划；见脱敏error_type/error_code，不据异常类归因供应商，不回退离线")
        except Exception as exc:
            # Exception messages may contain provider credentials or submitted
            # code. Store only its class and the last safe step, never str(exc).
            result.update(status="Error", provider="evals/transfer/", error_type=type(exc).__name__,
                          error_location=[{"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                                          for frame in traceback.extract_tb(exc.__traceback__)[-4:]])
        finally:
            if env:
                result.update(steps=env.steps, assertions=env.assertions, model_interactions=env.planner.records,
                              submissions=env.submissions, bank_reads=env.bank_reads, task=env.task,
                              baseline=env.baseline, final_bank=env.bank_state(), ledger=env.ledger())
                if hasattr(env, "browser_evidence"):
                    result["react"] = env.browser_evidence
                    if result["status"] != "Passed": result["react"]["status"] = result["status"]
                # Known synthetic credentials remain in memory until this final
                # redaction, including injected exceptions and returned codes.
                result = redact(result, known_secrets=env.secrets, free_text=True)
                env.close()
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result


def summarize(results):
    counts = Counter(r["status"] for r in results)
    standard = {r["scenario_id"]: r["status"] for r in results if r["standard"]}
    # Freeze the denominator even for a --case subset. Unrun standards do not
    # disappear to improve the rate.
    passed = sum(standard.get(ident) == "Passed" for ident in STANDARD_IDS)
    redline_checks = [v for r in results for v in r["assertions"] if v["name"].startswith("redline.")]
    missing = any(r["status"] in ("Blocked", "Error", "NotRun") for r in results) or len(results) != 153
    required_common = {"redline.no_unconfirmed_execution", "redline.no_duplicate_bank_call"}
    redline_missing = [r["id"] for r in results if not required_common <= {v["name"] for v in r["assertions"]}]
    questions = {f"TF-INP-{n:02}" for n in (1, 2, 3, 4, 5, 8, 12, 14)}
    question_results = {r["scenario_id"]: [v["passed"] for v in r["assertions"] if v["name"] == "input.correct_question" and v.get("scope") != "dedicated-field"]
                        for r in results if r["scenario_id"] in questions}
    question_passed = sum(bool(question_results.get(ident)) and all(question_results[ident]) for ident in questions)
    return {"counts": dict(counts), "samples_run": len(results), "expected_samples": 153,
            "standard_ids": STANDARD_IDS, "standard_passed": passed, "standard_total": len(STANDARD_IDS),
            "standard_rate": round(passed / len(STANDARD_IDS), 4), "standard_threshold_met": passed / len(STANDARD_IDS) >= .9,
            "redline_violations": sum(not v["passed"] for v in redline_checks),
            "redline_verdict": "Failed" if any(not v["passed"] for v in redline_checks) else "Unverified" if missing or redline_missing else "Passed",
            "redline_missing_samples": redline_missing,
            "missing_input_question_passed": question_passed, "missing_input_question_total": len(questions),
            "missing_input_question_rate": round(question_passed / len(questions), 4),
            "question_denominator_migration": "D2: INP09 precision rejection is separate; 9 to 8, samples remain 153",
            "amount_precision_sample": next((r["status"] for r in results if r["scenario_id"] == "TF-INP-09"), "NotRun"),
            "acceptance": "NotAccepted", "missing_evidence": missing,
            "note": "本票提供自动化能力；业务/页面/专业安全联合验收属于04及原12。"}


def capture_metadata(revision):
    root = Path(__file__).resolve().parents[2]
    files = sorted(Path(__file__).resolve().parent.glob("*.py"))
    digest = hashlib.sha256()
    for file in files:
        digest.update(file.name.encode())
        digest.update(file.read_bytes())
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", "backend", "frontend", "evals/transfer"],
                           cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
    return {"started_utc": datetime.now(timezone.utc).isoformat(), "revision": revision,
            "data_version": data_version(), "evaluator_source_sha256": digest.hexdigest(), "dirty_paths": dirty,
            "repeat_index": 1}


def write_report(path, results, *, revision, config_summary, platform=None, metadata=None):
    path.mkdir(parents=True, exist_ok=True)
    report = {**(metadata or capture_metadata(revision)), "configuration": config_summary,
              "summary": summarize(results), "results": results, "platform_regressions": platform or []}
    report["not_run_samples"] = [c["id"] for c in load_cases() if c["id"] not in {r["id"] for r in results}]
    (path / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = report["summary"]
    lines = ["# 普通转账自动化实际运行报告", "", f"代码：`{revision}`；数据：`{report['data_version']}`。",
             "", "本报告不是v0.3联合验收或Ringo专业安全结论。离线固定规划输出、真实GLM、HTTP与React分别记录。",
             "", f"样本：{len(results)}/153；状态：{summary['counts']}。",
             f"标准任务：{summary['standard_passed']}/21，≥90%：{summary['standard_threshold_met']}。",
             f"红线：{summary['redline_verdict']}；发现违规断言：{summary['redline_violations']}。缺证据不视为零违规验收通过。",
             "", "标准分母（运行前固定）：" + "、".join(STANDARD_IDS), "",
             "| 样本 | 执行层 | 实际结果 | 原因/未通过断言 | React | 专业安全 |",
             "|---|---|---|---|---|---|"]
    for r in results:
        reason = r.get("reason") or ", ".join(r.get("failed_assertions", [])) or r.get("error_type", "")
        lines.append(f"| {r['id']} | {r['layer']} | {r['status']} | {reason.replace('|', '/')} | {r['react']['status']} | NotRun |")
    lines += ["", "每次运行生成独立目录；保留首次失败，复跑不会覆盖旧报告。逐步骤、实际模型proposal、确认/任务/银行/账本和断言证据见同目录report.json。",
              "", "替身：离线固定proposal、按动作绑定的受控风险事实、指定读取/传输/日志中断及可控时钟。真实银行业务规则始终来自MockBankService。完整号码使用F36。",
              "", "平台回归：" + json.dumps(platform or [], ensure_ascii=False)]
    (path / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
