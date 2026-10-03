"""CLI: offline by default; --live-glm uses only the configured real provider."""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from catalog import load_cases
from runner import capture_metadata, run_case, write_report


def run_worker(case, directory, config_path, live, react_dist, evidence_directory):
    planner, blocker = None, None
    if live:
        try: planner, _ = live_planner(config_path)
        except Exception as exc: blocker = f"GLM配置不可用：{type(exc).__name__}"
    return run_case(case, directory, planner, blocker, react_dist, evidence_directory)


def live_planner(config_path):
    from app.agent_platform.local_demo import load_config
    from app.agent_platform.model import DeepAgentPlanner, ModelSettings
    from langchain_openai import ChatOpenAI
    config = load_config(config_path)
    if config.model_name != "glm-5.3" or config.base_url.rstrip("/") != "https://open.bigmodel.cn/api/coding/paas/v4":
        raise ValueError("EXPECTED_EXPLICIT_GLM_5_3_CODING_ENDPOINT")
    model = ChatOpenAI(model=config.model_name, api_key=config.api_key, base_url=config.base_url,
                       temperature=0, max_retries=0, timeout=60, use_responses_api=False)
    return DeepAgentPlanner(ModelSettings(model, "openai", config.model_name, "transfer-live-glm-v1")), {
        "provider": "智谱Coding Plan", "client_provider": "openai-compatible",
        "model": config.model_name, "endpoint": config.base_url,
        "stores": "per-sample temporary; config.data_directory is never used",
        "risk": "per-action evaluation fixtures; not production fraud detection"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-glm", action="store_true")
    parser.add_argument("--config", type=Path, default=Path(os.environ.get("BANK_LOCAL_CONFIG", ROOT / ".env.local-demo.json")))
    parser.add_argument("--case", action="append", help="Exact sample/scenario id; repeat to select. Default: all 153.")
    parser.add_argument("--output", type=Path, default=ROOT / ".mnemon" / "transfer-evals")
    parser.add_argument("--react-dist", type=Path, help="Existing real-api React build; enables actual browser fault scenarios (requires playwright chromium)")
    parser.add_argument("--jobs", type=int, default=1, choices=range(1, 5), help="1-4 isolated worker processes; each owns clocks and stores")
    args = parser.parse_args(argv)
    cases = load_cases()
    if args.case:
        selected = set(args.case)
        cases = [c for c in cases if c["id"] in selected or c["scenario_id"] in selected]
        if not cases: parser.error("No matching sample")
    planner, blocker = None, None
    config_summary = {"mode": "offline-fixed-proposal", "risk": "per-action evaluation fixture"}
    if args.live_glm:
        try: planner, config_summary = live_planner(args.config)
        except Exception as exc:
            blocker = f"真实GLM配置/依赖不可用：{type(exc).__name__}；未调用离线回退"
            config_summary = {"mode": "live-glm-blocked", "error_type": type(exc).__name__}
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    metadata = capture_metadata(revision)
    output = args.output / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    results = []
    with TemporaryDirectory(prefix="transfer-evaluation-") as temporary:
        def completed(result):
            results.append(result)
            print(f"{result['id']}: {result['status']}", flush=True)
            # Save after every sample so a process interruption preserves the
            # completed prefix. Final denominator is still 153/21.
            write_report(output, results, revision=revision, config_summary=config_summary, metadata=metadata)
        if args.jobs == 1 or blocker:
            for case in cases:
                completed(run_case(case, Path(temporary) / case["id"].replace("[", "-").replace("]", ""), planner, blocker,
                                   args.react_dist, output / "browser"))
        else:
            with ProcessPoolExecutor(max_workers=args.jobs) as pool:
                futures = [pool.submit(run_worker, case,
                    Path(temporary) / case["id"].replace("[", "-").replace("]", ""), args.config,
                    args.live_glm, args.react_dist, output / "browser") for case in cases]
                for future in as_completed(futures): completed(future.result())
    ordered = {case["id"]: index for index, case in enumerate(cases)}
    results.sort(key=lambda result: ordered[result["id"]])
    from platform_checks import run_platform_regressions
    with TemporaryDirectory(prefix="transfer-platform-") as temporary:
        platform = run_platform_regressions(Path(temporary), revision)
    report = write_report(output, results, revision=revision, config_summary=config_summary, platform=platform, metadata=metadata)
    print(f"Report: {output / 'report.md'}")
    print(report["summary"])
    return 1 if any(r["status"] != "Passed" for r in results + platform) else 0


if __name__ == "__main__":
    raise SystemExit(main())
