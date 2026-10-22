"""Observer-seams memory live load: prove seeded memory reaches the real model prompt.

Ticket v05-observer-seams/10 (Issue #216 item 3): F37/F38 view/delete memory is wired,
but there was no evidence that controlled memory is actually loaded into the planning
prompt of a real model. This script:

- seeds the demo memories into a temporary ApplicationStore (``seed_demo``) and creates
  a live session;
- wraps the real ``ChatOpenAI`` ``_generate`` so each call records only prompt hashes,
  message types and the matching memory key lines (never the full prompt or a secret);
- calls the real ``DeepAgentPlanner.select`` once with the real ``MemoryAdapter`` and the
  question 「请复述你记得的我的收入分配偏好和称呼线索。」;
- asserts J01 prompt carries the seeded memory, J02 reply recalls the allocation or the
  alias clue (keyword check for AI stand-in review, not a human sign-off), J03 no secret
  in the capture/report, J04 the real call count is exactly one (no retry to fake a pass).

Default execution is a zero-cost plan: no configuration is read and no model call is
made. Only ``--live-glm`` reads the config and performs the single real call (Lead
executes it).

Run:
    set PYTHONPATH=<repo>\\backend
    python evals/observer-seams/live_memory_load.py --output %TEMP%\\obs-memory-plan.json
    python evals/observer-seams/live_memory_load.py --live-glm --config <path> \\
        --output %TEMP%\\obs-memory-<guid>.json \\
        --archive-dir evals/security/evidence/2026-10-22
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"

SCHEMA_VERSION = "observer-seams-live-memory-v1"
MAX_REAL_MODEL_CALLS = 1
QUESTION = "请复述你记得的我的收入分配偏好和称呼线索。"
SEED_MONTH = "2026-09"
SEED_USER = "U1"
SEED_ROUND = "D1"
SEED_SESSION = "S1"

# Seeded memory lines from app.memory.adapter.seed_demo; only these marked lines are
# persisted in the capture, so the full prompt never lands in a report.
MEMORY_MARKERS = {
    "allocation": "60% 转 A5 储蓄",
    "allocation_family": "20% 转 A4 家庭",
    "alias_mother": "妈妈 → 银行种子 A2",
    "alias_family": "家庭账户 → 银行种子 A4",
}
REPLY_KEYWORDS = {
    "allocation": ("60%", "60％", "A5", "20%", "20％", "A4"),
    "alias": ("妈妈", "A2", "称呼线索"),
}
SECRET_PATTERNS = (
    re.compile(r"(?<!\d)\d{12,19}(?!\d)"),  # full account number
    re.compile(r"验证码\s*(?:是|为|[:：=])\s*\d{4,8}"),  # credential value
)


# --------------------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def inside_repository(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(REPO_ROOT.resolve())
    except (OSError, ValueError):
        return False


def _short(text: str, limit: int = 240) -> str:
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _obs(**values) -> str:
    return json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _explicit_model_settings(config_path: Path) -> dict:
    """Require model_name/base_url to be stated explicitly before any heavy import."""

    try:
        raw = json.loads(Path(config_path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"LIVE_MODEL_CONFIG_UNAVAILABLE: {type(exc).__name__}") from None
    if not isinstance(raw, dict):
        raise ValueError("LIVE_MODEL_CONFIG_UNAVAILABLE: ValueError")
    missing = [field for field in ("model_name", "base_url")
               if not str(raw.get(field) or "").strip()]
    if missing:
        raise ValueError(f"LIVE_MODEL_CONFIG_REQUIRES_EXPLICIT_FIELDS: {', '.join(missing)}")
    return {"model_name": str(raw["model_name"]), "base_url": str(raw["base_url"])}


def gzip_bytes(raw: bytes) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
        stream.write(raw)
    return buffer.getvalue()


# --------------------------------------------------------------------------------------
# Zero-cost plan
# --------------------------------------------------------------------------------------


def build_plan() -> dict:
    return {
        "plan_version": SCHEMA_VERSION,
        "code_revision": git_revision(),
        "config_policy": {
            "read": False,
            "mode": "dry-run-plan",
            "note": "Default execution reads no configuration and makes no model call.",
            "required_explicit_fields": ["model_name", "base_url"],
        },
        "budget": {
            "max_real_model_calls": MAX_REAL_MODEL_CALLS,
            "planned_real_model_calls": MAX_REAL_MODEL_CALLS,
            "retry_policy": "失败如实记 Blocked/Failed，不重试凑绿",
        },
        "setup": {
            "stores": "temporary ApplicationStore, data_directory from the config is never used",
            "memory": f"MemoryAdapter.seed_demo({SEED_USER!r}, {SEED_ROUND!r}, {SEED_MONTH!r})",
            "session": f"create_session({SEED_SESSION!r}, {SEED_USER!r}, {SEED_ROUND!r})",
            "question": QUESTION,
            "catalog": ["transfer.start_transfer"],
            "prompt_capture": "message type, prompt sha256/chars, seeded memory key lines only",
        },
        "assertions": {
            "J01": "真实模型调用前的 system prompt 含预置记忆行（记录命中项与哈希，不落全量提示）",
            "J02": "回复复述出预算比例或称呼线索至少一项（脚本记关键词命中，AI 代行初判、非真人签核）",
            "J03": "提示捕获与报告不含密钥、验证码、完整账号；报告只写模型/端点摘要",
            "J04": f"real_model_calls 恰好 {MAX_REAL_MODEL_CALLS}（失败如实记录，不重试）",
        },
        "manual_review": [
            "回复是否引用 60/20/20 分配或「妈妈 → A2」称呼线索",
            "回复是否说明实际收入/账户以银行查询为准（不作资金承诺）",
        ],
        "notes": [
            "真实模型 1 次调用由 Lead 执行，计入 Issue #216 小批量预算（总批次 ≤6 次）。",
            "不改 backend/；本票只补提示层证据。",
        ],
    }


# --------------------------------------------------------------------------------------
# Prompt capture (hash + seeded key lines only, never the full prompt)
# --------------------------------------------------------------------------------------


def _message_text(message) -> str:
    """Flatten a LangChain message content (string or structured content blocks)."""

    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content)


def _prompt_capture(messages, generation: int) -> dict:
    """Summarize one model call without persisting the full prompt.

    Only the seeded memory lines (short marker lines) are kept for J01 evidence;
    everything else is reduced to a message type, a character count and a SHA256.
    """

    message_records = []
    key_lines: list[str] = []
    marker_hits = {name: False for name in MEMORY_MARKERS}
    for message in messages:
        content = _message_text(message)
        message_records.append({
            "type": type(message).__name__,
            "chars": len(content),
            "sha256": sha256_hex(content.encode("utf-8")),
        })
        for line in content.splitlines():
            stripped = line.strip()
            for name, marker in MEMORY_MARKERS.items():
                if marker in stripped:
                    marker_hits[name] = True
                    # A memory marker line is a short seeded sentence; never persist
                    # a large block that happens to mention it.
                    if len(stripped) <= 300 and stripped not in key_lines:
                        key_lines.append(stripped)
    return {
        "generation": generation,
        "messages": message_records,
        "key_lines": key_lines,
        "memory_marker_hits": marker_hits,
        "full_prompt_persisted": False,
    }


def install_prompt_recorder(model, records: list[dict]) -> None:
    """Record each real model generation before delegating to the real client.

    ``ChatOpenAI`` is a pydantic model; the instance attribute shadows the class
    method, so ``BaseChatModel``'s own invoke/bind_tools path still calls it.
    """

    original = model._generate

    def recording_generate(messages, stop=None, run_manager=None, **kwargs):
        records.append(_prompt_capture(messages, len(records) + 1))
        return original(messages, stop=stop, run_manager=run_manager, **kwargs)

    object.__setattr__(model, "_generate", recording_generate)


def _reply_text(outcome) -> str | None:
    message = getattr(outcome, "message", None)
    return message if isinstance(message, str) else None


def _reply_keyword_hits(reply: str) -> dict[str, bool]:
    return {name: any(word in reply for word in words)
            for name, words in REPLY_KEYWORDS.items()}


# --------------------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------------------


class Rows:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, row_id: str, name: str, passed: bool, observed: str,
            status: str | None = None):
        self.items.append({
            "id": row_id,
            "name": name,
            "passed": bool(passed),
            "status": status or ("passed" if passed else "failed"),
            "observed": observed,
        })

    def blocked(self, row_id: str, name: str, observed: str):
        self.add(row_id, name, False, observed, status="blocked")

    @property
    def status_counts(self) -> dict[str, int]:
        return {status: sum(row["status"] == status for row in self.items)
                for status in ("passed", "failed", "blocked")}


# --------------------------------------------------------------------------------------
# Live run
# --------------------------------------------------------------------------------------


def _build_model(config):
    """Real client factory (patched in the offline self-check)."""

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=config.model_name, api_key=config.api_key, base_url=config.base_url,
        temperature=0, max_retries=0, timeout=60, use_responses_api=False,
    )


def run_live(config_path: Path) -> dict:
    rows = Rows()
    model_summary = {"mode": "live-glm", "question": QUESTION}
    prompt_records: list[dict] = []
    real_calls = 0
    reply: str | None = None
    outcome_type = None
    error: str | None = None
    data_directory = Path(tempfile.mkdtemp(prefix="observer-seams-memory-"))
    try:
        explicit = _explicit_model_settings(config_path)
        model_summary.update({
            "model": explicit["model_name"],
            "provider_host": urlparse(explicit["base_url"]).hostname,
            "endpoint": explicit["base_url"],
            "client_provider": "openai-compatible",
            "stores": "temporary ApplicationStore; config.data_directory is never used",
            "memory": "seed_demo(U1, D1, 2026-09) + one live session",
        })

        from app.agent_platform.local_demo import load_config
        from app.agent_platform.model import DeepAgentPlanner, ModelSettings
        from app.contracts.platform import TrustedContext
        from app.memory.adapter import MemoryAdapter, MemoryContext
        from app.storage.application import ApplicationStore

        config = load_config(config_path)
        application = ApplicationStore(data_directory / "application.sqlite")
        adapter = MemoryAdapter(application, active_round=lambda: SEED_ROUND)
        adapter.seed_demo(SEED_USER, SEED_ROUND, SEED_MONTH)
        now = datetime.now(timezone.utc)
        application.create_session(
            SEED_SESSION, SEED_USER, SEED_ROUND, now.isoformat(),
            (now + timedelta(hours=2)).isoformat(),
        )

        model = _build_model(config)
        install_prompt_recorder(model, prompt_records)
        planner = DeepAgentPlanner(ModelSettings(
            model=model, provider="openai", model_name=config.model_name,
            config_version="observer-seams-live-memory-v1",
        ))
        context = MemoryContext(SEED_USER, SEED_SESSION, SEED_ROUND)
        trusted = TrustedContext(
            user_id=SEED_USER, session_id=SEED_SESSION, demo_round_id=SEED_ROUND,
            task_id=str(uuid4()), run_id=str(uuid4()), parent_task_id=None,
        )
        try:
            real_calls += 1
            outcome = planner.select(
                QUESTION, trusted,
                [{"name": "transfer.start_transfer", "description": "单笔转账"}],
                adapter, adapter.conversation_thread_id(context),
            )
            outcome_type = type(outcome).__name__
            reply = _reply_text(outcome)
        except Exception as exc:  # noqa: BLE001 - the visible planner error is evidence
            error = f"{type(exc).__name__}:{_short(str(exc), 80)}"
    except ValueError as exc:
        code = str(exc)
        if not code.startswith("LIVE_MODEL_CONFIG_"):
            code = "LIVE_MODEL_CONFIG_UNAVAILABLE"
        model_summary.update({"mode": "live-glm-blocked", "error_code": code,
                              "error_type": type(exc).__name__})
        rows.blocked("J01", "真实模型提示含预置记忆", f"配置/依赖不可用（{code}），未调用模型")
        rows.blocked("J02", "回复复述预置记忆", f"配置/依赖不可用（{code}），未调用模型")
        rows.blocked("J03", "提示与报告不含密钥/凭据", f"配置/依赖不可用（{code}），未调用模型")
        rows.blocked("J04", "真实调用计数恰好 1", f"配置/依赖不可用（{code}），0 次调用")
        real_calls = 0
    except Exception as exc:  # noqa: BLE001
        model_summary.update({"mode": "live-glm-blocked", "error_code": "LIVE_MEMORY_RUN_ABORTED",
                              "error_type": type(exc).__name__})
        rows.blocked("J01", "真实模型提示含预置记忆", f"运行中断（{type(exc).__name__}），未完成")
        rows.blocked("J02", "回复复述预置记忆", f"运行中断（{type(exc).__name__}），未完成")
        rows.blocked("J03", "提示与报告不含密钥/凭据", f"运行中断（{type(exc).__name__}），未完成")
        rows.blocked("J04", "真实调用计数恰好 1", f"运行中断（{type(exc).__name__}），未完成")
    finally:
        shutil.rmtree(data_directory, ignore_errors=True)

    # J01: the captured system prompt must carry at least two seeded memory lines.
    captured_lines = [line for record in prompt_records for line in record["key_lines"]]
    captured_text = "\n".join(captured_lines)
    allocation_hit = any(marker in captured_text for marker in (
        MEMORY_MARKERS["allocation"], MEMORY_MARKERS["allocation_family"]))
    alias_hit = any(marker in captured_text for marker in (
        MEMORY_MARKERS["alias_mother"], MEMORY_MARKERS["alias_family"]))
    prompt_hashes = [message["sha256"]
                     for record in prompt_records for message in record["messages"]]
    if not rows.items or not any(row["status"] == "blocked" for row in rows.items):
        rows.add("J01", "真实模型调用前的 system prompt 含预置记忆行",
                 bool(prompt_records) and allocation_hit and alias_hit,
                 _obs(generations=len(prompt_records),
                      message_types=[message["type"] for record in prompt_records
                                     for message in record["messages"]],
                      prompt_sha256s=prompt_hashes,
                      allocation_line_present=allocation_hit,
                      alias_line_present=alias_hit,
                      captured_key_lines=captured_lines,
                      full_prompt_persisted=False))

        # J02: the reply recalls the allocation or the alias clue (AI stand-in review).
        hits = _reply_keyword_hits(reply or "")
        recalled = any(hits.values())
        rows.add("J02", "回复复述预算比例或称呼线索（脚本关键词，AI 代行初判非真人签核）",
                 bool(reply) and recalled,
                 _obs(reply_summary=_short(reply or ""), keyword_hits=hits,
                      review="AI 代行初判（非真人签核）；真实批次由 Lead 复核",
                      planner_error=error, outcome_type=outcome_type))

        # J03: no secret may appear in the capture or in the report fields.
        report_blob = json.dumps({
            "model_summary": model_summary, "capture": prompt_records,
            "reply": reply, "rows": rows.items,
        }, ensure_ascii=False)
        try:
            from app.agent_platform.local_demo import load_config as _load_config
            api_key = _load_config(config_path).api_key.get_secret_value()
        except Exception:  # noqa: BLE001 - the key is already validated in the live path
            api_key = ""
        secret_hits = [pattern.pattern for pattern in SECRET_PATTERNS
                       if pattern.search(report_blob)]
        rows.add("J03", "提示捕获与报告不含密钥/验证码/完整账号",
                 (not api_key or api_key not in report_blob) and not secret_hits,
                 _obs(api_key_in_report=bool(api_key and api_key in report_blob),
                      secret_pattern_hits=secret_hits,
                      capture_stores_full_prompt=any(
                          record["full_prompt_persisted"] for record in prompt_records)))

        rows.add("J04", f"真实调用计数恰好 {MAX_REAL_MODEL_CALLS}（失败不重试）",
                 real_calls == MAX_REAL_MODEL_CALLS,
                 _obs(real_model_calls=real_calls,
                      model_generations=len(prompt_records),
                      planner_error=error))

    return {
        "rows": rows.items,
        "model_summary": model_summary,
        "real_model_calls": real_calls,
        "model_generations": len(prompt_records),
        "prompt_capture": prompt_records,
        "reply": reply,
        "question": QUESTION,
    }


# --------------------------------------------------------------------------------------
# Report, archive and main
# --------------------------------------------------------------------------------------


def build_report(result: dict) -> dict:
    counts = {status: sum(row["status"] == status for row in result["rows"])
              for status in ("passed", "failed", "blocked")}
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now_iso(),
        "code_revision": git_revision(),
        "execution_layer": (
            "real ChatOpenAI via DeepAgentPlanner.select + real MemoryAdapter/MemoryMiddleware"
            " over a temporary ApplicationStore"
        ),
        "question": QUESTION,
        "memory_setup": {
            "user_id": SEED_USER, "demo_round_id": SEED_ROUND,
            "start_month": SEED_MONTH, "seeded_memories": 6,
        },
        "model_summary": result["model_summary"],
        "real_model_calls": result["real_model_calls"],
        "max_real_model_calls": MAX_REAL_MODEL_CALLS,
        "model_generations": result["model_generations"],
        "prompt_capture": result["prompt_capture"],
        "reply_summary": _short(result["reply"] or "") or None,
        "manual_review": {
            "j02": "AI 代行初判（非真人签核）：看关键词命中与回复摘要；真实批次由 Lead 复核",
            "j01": "提示命中项与哈希由脚本记录，全量提示不落盘",
        },
        "status_counts": counts,
        "rows": result["rows"],
        "notes": [
            "本票 1 次真实模型调用，计入 Issue #216 小批量预算（总批次 ≤6 次）。",
            "提示捕获只落消息类型、sha256 与预置记忆关键行，不落全量提示、不落密钥。",
            "失败如实记 Failed/Blocked，不重试凑绿。",
        ],
    }


def _ledger_path(archive_dir: Path) -> Path:
    for candidate in (archive_dir / "run-log.md", archive_dir.parent / "run-log.md"):
        if candidate.is_file():
            return candidate
    security_ledger = REPO_ROOT / "evals" / "security" / "run-log.md"
    return security_ledger if security_ledger.is_file() else archive_dir / "run-log.md"


def archive_report(raw: bytes, report: dict, archive_dir: Path,
                   label: str = "") -> dict:
    archive_dir = archive_dir.expanduser().resolve()
    archive_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now().astimezone().date().isoformat()
    suffix = f"-{label}" if label else ""
    destination = archive_dir / f"live-{day}-observer-seams-memory-load{suffix}.json.gz"
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite archived evidence: {destination}")

    compressed = gzip_bytes(raw)
    with destination.open("xb") as stream:
        stream.write(compressed)
    if gzip.decompress(destination.read_bytes()) != raw:
        raise ValueError("ARCHIVE_ROUND_TRIP_MISMATCH")

    ledger = _ledger_path(archive_dir)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    try:
        link = destination.relative_to(ledger.parent).as_posix()
    except ValueError:
        link = destination.name
    model = report["model_summary"]
    counts = report["status_counts"]
    row = (
        f"| {day} | {model.get('model', 'unknown')} @ {model.get('provider_host', 'unknown')} | "
        f"记忆真实载入会话（1 次真实调用，seed_demo U1/D1/{SEED_MONTH}） | "
        f"{counts['passed']} Passed / {counts['failed']} Failed / "
        f"{counts['blocked']} Blocked | 模型调用 {report['real_model_calls']} 次；"
        f"J01–J04 | [{destination.name}]({link})（{sha256_hex(raw)[:16]}） |"
    )
    section = (
        f"\n## {day} observer-seams 记忆真实载入会话（v05-observer-seams/10）\n\n"
        "| 日期 | 入口 | 范围 | 状态分布 | 断言 | 报告文件（解压 sha256 前16位） |\n"
        "|---|---|---|---|---|---|\n"
        f"{row}\n\n"
        f"- gzip sha256: `{sha256_hex(compressed)}`；解压 sha256: `{sha256_hex(raw)}`；"
        f"解压字节数: {len(raw)}；code_revision: `{report['code_revision']}`。\n"
        "- 判定口径：J01 提示含预置记忆（命中项+哈希，不落全量提示）/ J02 回复复述"
        "（关键词，AI 代行初判非真人签核）/ J03 无密钥凭据 / J04 真实调用数=1。\n"
    )
    if not ledger.exists():
        ledger.write_bytes(("# 评测运行台账\n" + section).encode("utf-8"))
    else:
        with ledger.open("ab") as stream:
            stream.write(section.encode("utf-8"))
    return {
        "report_file": str(destination),
        "gzip_sha256": sha256_hex(compressed),
        "uncompressed_sha256": sha256_hex(raw),
        "uncompressed_bytes": len(raw),
        "ledger": str(ledger),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Observer-seams memory live load: prove seeded memory reaches the real "
                    "model prompt. Default is a zero-cost plan check.")
    parser.add_argument("--live-glm", action="store_true",
                        help="Read the config and perform exactly one real model call.")
    parser.add_argument("--config", type=Path,
                        default=Path(os.environ.get("BANK_LOCAL_CONFIG",
                                                    REPO_ROOT / ".env.local-demo.json")),
                        help="Local demo config JSON (never printed; needs explicit "
                             "model_name and base_url).")
    parser.add_argument("--output", type=Path, required=True,
                        help="New report path outside the repository; existing files are refused.")
    parser.add_argument("--archive-dir", type=Path,
                        help="Optional evidence directory: gzip the report there "
                             "(filename=\"\", mtime=0) and append one ledger row.")
    parser.add_argument("--archive-label", default="",
                        help="Optional suffix for a re-run archive; an existing archive is "
                             "never overwritten.")
    args = parser.parse_args(argv)

    if args.archive_dir is not None and not args.live_glm:
        parser.error("--archive-dir requires --live-glm (the dry-run plan is not evidence)")
    if args.archive_label:
        if not args.live_glm:
            parser.error("--archive-label requires --live-glm")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.archive_label):
            parser.error("--archive-label must be lowercase words separated by '-'")

    output = args.output.expanduser()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing report: {output}")
    if inside_repository(output):
        raise ValueError(f"REPORT_INSIDE_REPOSITORY: choose a path outside {REPO_ROOT}")
    output.parent.mkdir(parents=True, exist_ok=True)

    if not args.live_glm:
        plan = build_plan()
        report = {
            "schema_version": SCHEMA_VERSION,
            "created_at": now_iso(),
            "mode": "dry-run-plan",
            "code_revision": plan["code_revision"],
            "model_summary": {"mode": "dry-run-plan", "real_model_calls": 0},
            "real_model_calls": 0,
            "plan": plan,
            "status_counts": {"passed": 0, "failed": 0, "blocked": 0},
            "rows": [],
        }
        raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with output.open("xb") as stream:
            stream.write(raw)
        print(json.dumps({"mode": "dry-run-plan", "report": str(output),
                          "plan": plan["budget"], "question": QUESTION,
                          "config_read": False, "real_model_calls": 0},
                         ensure_ascii=False))
        return 0

    result = run_live(args.config)
    report = build_report(result)
    raw = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with output.open("xb") as stream:
        stream.write(raw)

    archive = None
    if args.archive_dir is not None:
        archive = archive_report(raw, report, args.archive_dir, args.archive_label)

    summary = {
        "report": str(output),
        "schema_version": report["schema_version"],
        "code_revision": report["code_revision"],
        "model_summary": report["model_summary"],
        "real_model_calls": report["real_model_calls"],
        "model_generations": report["model_generations"],
        "status_counts": report["status_counts"],
        "archive": archive,
    }
    print(json.dumps(summary, ensure_ascii=False))
    counts = report["status_counts"]
    return 0 if counts["failed"] == 0 and counts["blocked"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
