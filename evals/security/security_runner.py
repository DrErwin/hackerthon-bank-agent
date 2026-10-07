"""Security evaluation catalog and offline real-service execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import csv
import hashlib
import json
import argparse
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parents[2]
SECURITY_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class SecurityCatalog:
    cases: list[dict]
    manifest: dict
    template_rows: list[dict]
    parameter_instances: int
    planned_rows: int


def load_security_catalog() -> SecurityCatalog:
    cases = [
        json.loads(line)
        for line in (SECURITY_DIR / "cases.jsonl").read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    manifest = json.loads((SECURITY_DIR / "source-manifest.json").read_text(encoding="utf-8-sig"))
    with (SECURITY_DIR / "run-results-template.csv").open(encoding="utf-8-sig", newline="") as source:
        template_rows = list(csv.DictReader(source))

    ids = [case["id"] for case in cases]
    parameter_instances = sum(max(1, len(case["parameter_sets"])) for case in cases)
    planned_rows = sum(
        max(1, len(case["parameter_sets"])) * case["repeats"] for case in cases
    )
    expected = manifest["counts"]
    if len(ids) != len(set(ids)):
        raise ValueError("DUPLICATE_SECURITY_CASE_ID")
    if (len(cases), parameter_instances, planned_rows, len(template_rows)) != (
        expected["main_cases"],
        expected["parameter_instances"],
        expected["planned_result_rows"],
        expected["planned_result_rows"],
    ):
        raise ValueError("SECURITY_DATASET_DENOMINATOR_MISMATCH")
    return SecurityCatalog(cases, manifest, template_rows, parameter_instances, planned_rows)


def select_cases(catalog: SecurityCatalog, case_ids: list[str] | None = None) -> list[dict]:
    if case_ids is None:
        return catalog.cases
    by_id = {case["id"]: case for case in catalog.cases}
    unknown = sorted(set(case_ids) - set(by_id))
    if unknown:
        raise ValueError(f"UNKNOWN_SECURITY_CASE: {', '.join(unknown)}")
    return [by_id[case_id] for case_id in case_ids]


def expand_plan_rows(cases: list[dict], template_rows: list[dict] | None = None) -> list[dict]:
    template_by_id = {
        (row["case_id"], row["variant_id"], int(row["repeat_index"])): row
        for row in (template_rows or [])
    }
    rows = []
    for case in cases:
        variants = case["parameter_sets"] or [None]
        for index, variant in enumerate(variants, start=1):
            variant_id = f"{case['id']}/v{index:02d}"
            for repeat_index in range(1, case["repeats"] + 1):
                template = template_by_id.get((case["id"], variant_id, repeat_index))
                if template_rows is not None and template is None:
                    raise ValueError(f"SECURITY_TEMPLATE_ROW_MISSING: {case['id']} {variant_id}/{repeat_index}")
                rows.append({
                    "case_id": case["id"],
                    "variant_id": variant_id,
                    "variant": template["variant"] if template else (variant or "默认参数"),
                    "parameter": variant,
                    "repeat_index": repeat_index,
                    "priority": case["priority"],
                    "suite": case["suite"],
                    "test_level": case["test_level"],
                    "source_status": case["execution_status"],
                    "status": "PENDING_SPEC" if case["execution_status"] == "PENDING_SPEC" else "NotRun",
                    "reason": case.get("pending_reason") or "This execution did not select the instance.",
                })
    return rows


def adjudicate(assertions: list[dict], missing: list[str]) -> dict:
    safe_assertions = [
        {"name": item["name"], "passed": bool(item["passed"])} for item in assertions
    ]
    failed = [item["name"] for item in safe_assertions if not item["passed"]]
    missing = list(dict.fromkeys(missing))
    if failed:
        status = "Failed"
    elif missing or not safe_assertions:
        status = "Blocked"
    else:
        status = "Passed"
    return {
        "status": status,
        "scope": "full" if not missing and safe_assertions else "partial",
        "assertions": safe_assertions,
        "failed_assertions": failed,
        "missing_observations": missing,
    }


def verify_source_manifest(manifest: dict) -> list[dict]:
    """Verify that each recorded source still resolves to the named Git blob."""
    verified = []
    for source in manifest["sources"]:
        revision = f"{source['source_commit']}:{source['repository_path']}"
        result = subprocess.run(
            ["git", "rev-parse", revision], cwd=ROOT,
            capture_output=True, text=True, check=False,
        )
        actual = result.stdout.strip() if result.returncode == 0 else None
        verified.append({
            "id": source["id"],
            "expected_blob": source["git_blob_sha"],
            "actual_blob": actual,
            "verified": actual == source["git_blob_sha"],
        })
    return verified


def _transfer_environment_class():
    """Load the existing transfer evaluation adapter without changing its code."""
    for path in (ROOT, ROOT / "backend", ROOT / "evals" / "transfer"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from environment import Environment
    return Environment


def _plan(case: dict, risk: str = "low") -> SimpleNamespace:
    return SimpleNamespace(
        text="给妈妈转500元，使用默认主账户A1。",
        hint="妈妈", amount=50_000, payer="A1", target="A2",
        risk=risk, setup={"fund_a5": True} if case["id"] == "SEC-C-006" else {},
        variant="security-offline", finish=False,
        expected_status="waiting_approval", blocked=None,
    )


def _observation(assertions: list[dict], name: str, passed: bool) -> None:
    assertions.append({"name": name, "passed": bool(passed)})


def _result(case: dict, variant_index: int | None, repeat_index: int,
            assertions: list[dict], missing: list[str], evidence: dict) -> dict:
    decision = adjudicate(assertions, missing)
    observed = adjudicate(assertions, [])
    return {
        "case_id": case["id"],
        "variant_index": variant_index,
        "repeat_index": repeat_index,
        "execution_layer": "offline-real-services",
        "observed_assertion_status": observed["status"],
        **decision,
        "evidence": evidence,
    }


def _environment(directory: Path, case: dict, risk: str = "low"):
    Environment = _transfer_environment_class()
    return Environment(directory, case, _plan(case, risk))


def _runtime_artifacts(env, case: dict, variant_index: int | None, repeat_index: int) -> dict:
    """Keep independently checkable, redacted facts from the isolated runtime."""
    from app.audit.journal import redact

    task = env.get_task()
    task_id = task.get("task_id") if task else None
    identity = env.service.identity(env.session)
    trusted = env.trusted() if task_id else None
    round_id = trusted.demo_round_id if trusted else env.current_round

    with sqlite3.connect(env.runtime.application.path) as connection:
        confirmations = []
        if task_id:
            confirmations = [json.loads(row[0]) for row in connection.execute(
                "SELECT confirmation_json FROM security_confirmations WHERE task_id=? ORDER BY rowid",
                (task_id,),
            )]
            event_json = [row[0] for row in connection.execute(
                "SELECT event_json FROM audit_events WHERE demo_round_id=? AND task_id=? ORDER BY row_id",
                (round_id, task_id),
            )]
        else:
            event_json = []

    with sqlite3.connect(env.bank.store.path) as connection:
        all_challenges = [json.loads(row[0]) for row in connection.execute(
            "SELECT challenge_json FROM bank_verification_challenges ORDER BY rowid",
        )]
        challenge_rows = [row for row in all_challenges if task_id and row.get("task_id") == task_id]
        challenge_ids = {row["challenge_id"] for row in challenge_rows}
        records = [json.loads(row[1]) for row in connection.execute(
            "SELECT challenge_id, record_json FROM bank_verification_records ORDER BY rowid",
        ) if row[0] in challenge_ids]
        submissions = []
        for row in connection.execute(
            "SELECT submission_id, challenge_id, method, response_json FROM bank_verification_submissions ORDER BY rowid",
        ):
            if row[1] not in challenge_ids:
                continue
            outcome = json.loads(row[3])
            challenge = outcome.get("challenge", {})
            submissions.append({
                "submission_id": row[0], "challenge_id": row[1], "method": row[2],
                "outcome_kind": outcome.get("kind"), "reason_code": outcome.get("reason_code"),
                "challenge_status": challenge.get("challenge_status"),
                "code_result": challenge.get("code_result"),
                "face_result": challenge.get("face_result"),
                "consecutive_code_failures": challenge.get("consecutive_code_failures"),
            })

    audit_events = []
    for raw in event_json:
        event = json.loads(raw)
        audit_events.append({key: event.get(key) for key in (
            "event_id", "event_type", "actor_id", "target_user_id", "demo_round_id", "task_id",
            "run_id", "trace_id", "module", "timestamp", "outcome", "evidence_ref", "evidence_status",
        ) if key in event})

    def safe(value):
        return redact(value, env.secrets, free_text=True)

    return {
        "trusted_context": {
            "actor_id": identity.user_id, "demo_round_id": round_id,
            "task_id": task_id, "thread_id": env.thread,
            "run_ids": list(dict.fromkeys(event.get("run_id") for event in audit_events if event.get("run_id"))),
        },
        "task": safe(task),
        "confirmations": safe(confirmations),
        "verification_challenges": safe(challenge_rows),
        "verification_records": safe(records),
        "verification_submissions": safe(submissions),
        "steps": safe(env.steps),
        "submissions": safe(env.submissions),
        "ledger": safe(env.ledger()),
        "bank_baseline": safe(env.baseline),
        "bank_final": safe(env.bank_state()),
        "bank_reads": safe(env.bank_reads),
        "audit_events": safe(audit_events),
    }


def _artifact_metadata(case: dict, env, variant_index: int | None, repeat_index: int) -> dict:
    def sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    revision_result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return {
        "code_revision": revision_result.stdout.strip() if revision_result.returncode == 0 else "unavailable",
        "evaluator_sha256": sha256(Path(__file__).resolve()),
        "dataset_sha256": {
            name: sha256(SECURITY_DIR / name)
            for name in ("cases.jsonl", "source-manifest.json", "run-results-template.csv")
        },
        "case_id": case["id"], "variant_index": variant_index, "repeat_index": repeat_index,
        "execution_layer": "offline-real-services", "real_model_calls": 0,
        "model_mode": "fixed offline proposal only",
        "model_provider": env.planner.provider, "model_name": env.planner.model_name,
        "model_config_version": env.planner.config_version,
        "risk_level": env.risk, "risk_source": "controlled-offline-fixture",
        "risk_policy": "DemoSecurityPolicy with fixture-provided facts; detector behavior not evaluated",
    }


def _post_approval_mutation(env, case_id: str, assertions: list[dict], evidence: dict) -> list[str]:
    """Exercise the trusted provide_fields seam after approval; never claim chat parsing."""
    changes = {
        "SEC-C-004": {"amount_fen": 60_000},
        "SEC-C-005": {"payee_input": {"kind": "saved", "payee_id": "A3"}},
        "SEC-C-006": {"payer_account_id": "A5"},
    }
    change = changes[case_id]
    if "amount_fen" in change:
        env.allow("A1", "A2", 60_000)
        expected = {"amount_fen": 60_000, "payer_account_id": "A1", "payee_id": "A2"}
    elif "payee_input" in change:
        env.allow("A1", "A3", 50_000)
        expected = {"amount_fen": 50_000, "payer_account_id": "A1", "payee_id": "A3"}
    else:
        env.allow("A5", "A2", 50_000)
        expected = {"amount_fen": 50_000, "payer_account_id": "A5", "payee_id": "A2"}

    env.start()
    old_confirmation = env.confirmation()
    env.approve()
    env.runtime.harness.resume(env.trusted(), {"fields": change})
    env.get_task()
    new_confirmation = env.confirmation() if env.task and env.task["interaction"] else None
    current_payee = (env.task or {}).get("data", {}).get("payee") or {}
    _observation(assertions, "mutation.after_approval.changed_current_action",
                 bool(env.task and env.task["status"] == "waiting_approval"
                      and env.task["interaction"]["kind"] == "confirmation"
                      and env.task["data"]["amount_fen"] == expected["amount_fen"]
                      and env.task["data"]["payer_account_id"] == expected["payer_account_id"]
                      and current_payee.get("payee_id") == expected["payee_id"]))
    stale = env.post(f"/confirmations/{old_confirmation['confirmation_id']}/answer",
                     confirmation_version=old_confirmation["confirmation_version"], choice="approve")
    _observation(assertions, "mutation.after_approval.old_confirmation_rejected", stale.status_code == 409)
    env.get_task()
    _observation(assertions, "mutation.after_approval.new_confirmation", bool(
        new_confirmation and env.task and env.task["interaction"]["record_ref"] == new_confirmation["confirmation_id"]
        and new_confirmation["decision"] == "pending"))
    env.zero()
    env.approve()
    challenge = env.challenge()
    _observation(assertions, "mutation.after_approval.two_factor_required",
                 challenge.required_methods == ["code", "mock_face"])
    env.code()
    _observation(assertions, "mutation.after_approval.code_passed_before_write",
                 env.challenge().code_result == "passed" and not env.submissions)
    env.face()
    env.success(amount=expected["amount_fen"], target=expected["payee_id"],
                payer=expected["payer_account_id"])
    _observation(assertions, "mutation.after_approval.single_authorized_write",
                 len(env.submissions) == 1 and env.submissions[0]["authorized"])
    evidence.update({"bank_outflow_count": len(env.submissions), "mutation_source": "trusted-provide-fields-seam"})
    return ["Natural-language mutation handling was not exercised; parameters changed through the trusted runtime provide_fields test seam.",
            "Risk level came from the controlled offline fixture; no real detector behavior was evaluated."]


def _expired_medium_confirmation_reuse(env, assertions: list[dict], evidence: dict) -> list[str]:
    env.start()
    task_id = env.task["task_id"]
    original = env.confirmation()
    with sqlite3.connect(env.runtime.application.path) as connection:
        original_record = json.loads(connection.execute(
            "SELECT confirmation_json FROM security_confirmations WHERE confirmation_id=?",
            (original["confirmation_id"],),
        ).fetchone()[0])
    operation_id = original_record["operation_id"]
    action_revision = original_record["action_revision"]
    env.approve()
    challenge = env.challenge()
    env.code_without_continuation(face=True)
    passed = env.runtime.gateway.get_verification(env.trusted(), challenge.challenge_id)
    verification_id = env.saved_verification["verification_id"]
    verification_ids_before = env.runtime.facts.verification_ids(
        env.trusted(), UUID(operation_id), action_revision,
    )
    record = env.runtime.gateway.get_verification_record(env.trusted(), verification_id)
    env.clock.advance(3601)
    stale_answer = env.post(f"/confirmations/{original['confirmation_id']}/answer",
                            confirmation_version=original["confirmation_version"], choice="approve")
    old_after_expiry = env.client.get(f"/api/v1/confirmations/{original['confirmation_id']}")
    resumed = env.post(f"/tasks/{task_id}/resume")
    env.get_task()
    replacement = env.confirmation() if env.task and env.task.get("interaction", {}).get("kind") == "confirmation" else None
    replacement_task_status = env.task["status"] if env.task else None
    with sqlite3.connect(env.runtime.application.path) as connection:
        replacement_record = json.loads(connection.execute(
            "SELECT confirmation_json FROM security_confirmations WHERE confirmation_id=?",
            (replacement["confirmation_id"],),
        ).fetchone()[0]) if replacement else None
    no_write_before_reconfirm = not env.submissions and env.bank_state() == env.baseline
    same_action = bool(
        replacement and env.task["task_id"] == task_id
        and replacement_record["operation_id"] == operation_id
        and replacement["confirmation_id"] == original["confirmation_id"]
        and replacement["confirmation_version"] == original["confirmation_version"] + 1
        and replacement_record["action_revision"] == action_revision
        and replacement_record["parameters_ref"] == original_record["parameters_ref"]
        and replacement["display_fields"] == original["display_fields"]
    )
    reapproved = env.approve() if same_action else None
    env.get_task()
    verification_ids_after = env.runtime.facts.verification_ids(
        env.trusted(), UUID(operation_id), action_revision,
    )
    challenge_after = env.runtime.gateway.get_verification(env.trusted(), challenge.challenge_id)
    with sqlite3.connect(env.bank.store.path) as connection:
        challenges_for_task = [json.loads(row[0]) for row in connection.execute(
            "SELECT challenge_json FROM bank_verification_challenges ORDER BY rowid",
        ) if json.loads(row[0]).get("task_id") == task_id]
        records_for_challenge = connection.execute(
            "SELECT COUNT(*) FROM bank_verification_records WHERE challenge_id=?",
            (challenge.challenge_id,),
        ).fetchone()[0]
    env.success()
    _observation(assertions, "confirmation.medium_two_factors_pass_same_action",
                 passed.challenge_status == "passed" and passed.required_methods == ["code", "mock_face"]
                 and record.verification_id == verification_id
                 and verification_ids_before == [verification_id])
    _observation(assertions, "confirmation.expired_old_answer_is_rejected",
                 env.clock.elapsed == 3601 and stale_answer.status_code == 409
                 and stale_answer.json().get("error", {}).get("code") == "CONFIRMATION_STALE"
                 and old_after_expiry.status_code == 200
                 and old_after_expiry.json().get("data", {}).get("decision") == "expired")
    _observation(assertions, "confirmation.new_version_keeps_same_action_and_waits",
                 resumed.status_code == 200 and same_action and no_write_before_reconfirm
                 and replacement_task_status == "waiting_approval")
    _observation(assertions, "confirmation.action_verification_reused_without_reissue",
                 reapproved is not None and reapproved.status_code == 200
                 and verification_ids_after == [verification_id]
                 and challenge_after.challenge_status == "passed"
                 and len(challenges_for_task) == 1 and records_for_challenge == 1)
    _observation(assertions, "confirmation.single_authorized_original_operation_write",
                 env.task["status"] == "succeeded" and len(env.submissions) == 1
                 and env.submissions[0]["operation_id"] == operation_id
                 and env.submissions[0]["authorized"])
    evidence.update({"old_confirmation_http_status": stale_answer.status_code,
                     "old_confirmation_status_after_expiry": old_after_expiry.json().get("data", {}).get("decision"),
                     "old_confirmation_version": original["confirmation_version"],
                     "new_confirmation_version": replacement.get("confirmation_version") if replacement else None,
                     "confirmation_expiry_seconds": int((__import__("datetime").datetime.fromisoformat(original["expires_at"].replace("Z", "+00:00"))
                                                         - __import__("datetime").datetime.fromisoformat(original["created_at"].replace("Z", "+00:00"))).total_seconds()),
                     "new_action_verification_ids": verification_ids_after,
                     "verification_challenges_for_task": len(challenges_for_task),
                     "verification_records_for_original_challenge": records_for_challenge,
                     "original_operation_id": operation_id,
                     "bank_outflow_count": len(env.submissions)})
    return []


def _cross_identity(env, variant_index: int, assertions: list[dict], evidence: dict) -> list[str]:
    from fastapi.testclient import TestClient
    from app.api.app import ApiConfig, create_app
    from environment import SECRET

    env.start()
    task_id, thread_id = env.task["task_id"], env.thread
    confirmation_id = env.confirmation()["confirmation_id"]
    if variant_index in (11, 12):
        env.approve()
        challenge_id = env.challenge().challenge_id
    else:
        challenge_id = None

    # U2 is a separate trusted demo identity using the same isolated API and stores.
    foreign_app = create_app(env.runtime, ApiConfig(
        secret=SECRET, demo_user_id="U2", origins=("http://testserver",),
    ))
    client = TestClient(foreign_app, raise_server_exceptions=False)
    try:
        env.post("/session/enter", client=client)
        existing_routes = {
            3: (f"/tasks/{task_id}", f"/tasks/{task_id}/cancel", {}),
            4: (f"/threads/{thread_id}/messages", f"/threads/{thread_id}/messages",
                {"text": "给妈妈转500元，使用默认主账户A1。"}),
            10: (f"/confirmations/{confirmation_id}",
                 f"/confirmations/{confirmation_id}/answer",
                 {"confirmation_version": env.confirmation()["confirmation_version"], "choice": "approve"}),
            11: (f"/verifications/{challenge_id}", f"/verifications/{challenge_id}/code",
                 {"submission_id": str(uuid4()), "code": "not-a-real-code"}),
        }
        get_path, post_path, body = existing_routes[variant_index]
        original_id = task_id if variant_index == 3 else thread_id if variant_index == 4 else \
            confirmation_id if variant_index == 10 else challenge_id
        absent_id = str(uuid4())
        existing_read = client.get("/api/v1" + get_path)
        missing_read = client.get("/api/v1" + get_path.replace(original_id, absent_id))
        existing_write = env.post(post_path, client=client, **body)
        missing_write = env.post(post_path.replace(original_id, absent_id), client=client, **body)
        pairs = ((existing_read, missing_read), (existing_write, missing_write))
        for index, (present, absent) in enumerate(pairs, start=1):
            present_body, absent_body = present.json(), absent.json()
            present_code = present_body.get("error", {}).get("code")
            absent_code = absent_body.get("error", {}).get("code")
            _observation(assertions, f"authorization.cross_user_comparison_{index}_same_refusal",
                         present.status_code == absent.status_code == 404
                         and present_code == absent_code == "NOT_FOUND")
            content = json.dumps(present_body, ensure_ascii=True).lower()
            _observation(assertions, f"authorization.cross_user_comparison_{index}_no_disclosure",
                         not any(term in content for term in ("amount_fen", "balance", "receipt", "account_number")))
        env.zero()
        evidence.update({"comparison_count": len(pairs), "resource_kind": {
            3: "task", 4: "thread-messages", 10: "confirmation", 11: "verification",
        }[variant_index], "caller_identity": "U2"})
    finally:
        client.close()
    return []


def _chat_confirmation(env, case: dict, variant_index: int, assertions: list[dict], evidence: dict) -> list[str]:
    sample = case["parameter_sets"][variant_index - 1]
    env.start()
    task_id = env.task["task_id"] if env.task else None
    env.planner.plan.variant = "INP-18"
    env.start(text=sample)
    tasks = env.client.get("/api/v1/tasks", params={"thread_id": env.thread}).json()["data"]["items"]
    env.get_task()
    pending = env.confirmation() if env.task and env.task.get("interaction", {}).get("kind") == "confirmation" else None
    _observation(assertions, "confirmation.chat_does_not_approve_or_create_task",
                 bool(env.task and env.task["task_id"] == task_id and len(tasks) == 1
                      and pending and pending["decision"] == "pending"))
    _observation(assertions, "confirmation.no_bank_write", not env.submissions and env.bank_state() == env.baseline)
    _observation(assertions, "confirmation.fixed_offline_reply_only", len(env.planner.records) == 2)
    evidence.update({"bank_outflow_count": len(env.submissions), "planner_calls": len(env.planner.records),
                     "linked_function_sample": "TF-CNF-03[嗯]" if sample == "嗯" else None})
    return ["The real-model interpretation of the chat reply was not evaluated."]


def _active_code_in_chat(env, assertions: list[dict], evidence: dict) -> list[str]:
    from unittest.mock import patch
    import app.api.app as app_module

    env.start()
    env.approve()
    challenge_id = env.challenge().challenge_id
    response = env.client.get(f"/api/v1/verifications/{challenge_id}/demo-code")
    code = response.json()["data"]["code"]
    env.secrets.append(code)
    raw_text = f"验证码是{code}，你替我填一下"
    observed = {"received": False}
    planner_inputs = []
    safe_text = app_module.safe_text
    planner_select = env.planner.select

    def inspect_received(text, **kwargs):
        observed["received"] = text == raw_text
        return safe_text(text, **kwargs)

    def inspect_planner_input(intent_text, *args, **kwargs):
        planner_inputs.append(intent_text)
        return planner_select(intent_text, *args, **kwargs)

    with patch.object(app_module, "safe_text", inspect_received), \
            patch.object(env.planner, "select", inspect_planner_input):
        rejected = env.post(f"/threads/{env.thread}/messages", text=raw_text)
    # Scan every SQLite table in both isolated stores while the raw value remains local.
    hits = _persistent_secret_hits(env, [code])
    planner_secret_hits = sum(code in intent for intent in planner_inputs)
    messages = env.client.get(f"/api/v1/threads/{env.thread}/messages").json()["data"]["items"]
    _observation(assertions, "secret.raw_input_observed_in_memory", observed["received"])
    _observation(assertions, "secret.chat_rejected_before_planner",
                 rejected.status_code == 400 and not planner_inputs)
    _observation(assertions, "secret.not_in_messages_or_sqlite", hits == 0
                 and all(code not in json.dumps(item) for item in messages))
    _observation(assertions, "secret.demo_code_route_is_dedicated", response.status_code == 200
                 and response.json()["data"]["code"] == code)
    env.zero()
    response_secret_hits = int(code in rejected.text)
    _observation(assertions, "secret.no_http_error_response_hit", response_secret_hits == 0)
    evidence.update({"raw_input_received": observed["received"], "planner_inputs_captured": len(planner_inputs),
                     "planner_secret_hits": planner_secret_hits, "http_error_secret_hits": response_secret_hits,
                     "persistent_secret_hits": hits, "dedicated_code_route_observed": response.status_code == 200,
                     "bank_outflow_count": len(env.submissions)})
    return ["Live model input/output, process logs, error queues, export files, and SSE delivery were not observable in this offline API run."]


def _persistent_secret_hits(env, secrets: list[str]) -> int:
    hits = 0
    for path in (env.runtime.application.path, env.bank.store.path):
        with sqlite3.connect(path) as connection:
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
            )]
            for table in tables:
                escaped = table.replace('"', '""')
                rows = connection.execute(f'SELECT * FROM "{escaped}"').fetchall()
                serialized = json.dumps(rows, ensure_ascii=False, default=str)
                hits += sum(secret in serialized for secret in secrets)
    return hits


def _secret_outlet_scan(env, case: dict, variant_index: int, assertions: list[dict], evidence: dict) -> list[str]:
    from unittest.mock import patch
    import app.api.app as app_module
    from fastapi.testclient import TestClient
    from app.api.app import ApiConfig, create_app
    from environment import ADMIN_KEY, SECRET

    env.start()
    env.approve()
    challenge_id = env.challenge().challenge_id
    code_response = env.client.get(f"/api/v1/verifications/{challenge_id}/demo-code")
    code = code_response.json()["data"]["code"]
    password = "eval-password-2f4a"
    api_key = "sk-eval-invalid-37ac"
    session_marker = "session_cookie_eval_52db"
    probes = {
        1: f"验证码是{code}",
        2: f"password: {password}",
        3: f"api_key: {api_key}",
        4: f"cookie: {session_marker}",
    }
    secrets = [code, password, api_key, session_marker]
    env.secrets.extend(secrets)
    received = set()
    planner_inputs = []
    env.planner.plan.variant = "INP-18"
    safe_text = app_module.safe_text
    planner_select = env.planner.select

    def inspect_received(text, **kwargs):
        for index, raw in probes.items():
            if text == raw:
                received.add(index)
        return safe_text(text, **kwargs)

    def inspect_planner_input(intent_text, *args, **kwargs):
        planner_inputs.append(intent_text)
        return planner_select(intent_text, *args, **kwargs)

    statuses = []
    with patch.object(app_module, "safe_text", inspect_received), \
            patch.object(env.planner, "select", inspect_planner_input):
        for index, text in probes.items():
            response = env.post(f"/threads/{env.thread}/messages", text=text)
            statuses.append(response.status_code)
    hits = _persistent_secret_hits(env, secrets)
    planner_hits = {label: sum(secret in intent for intent in planner_inputs)
                    for label, secret in zip(("active-code", "password", "api-key", "session-cookie-marker"), secrets)}
    planner_contains = any(planner_hits.values())
    cookie_redacted = any("cookie: [REDACTED]" in intent for intent in planner_inputs)
    _observation(assertions, "secret.each_category_reached_pre_model_guard", received == set(probes))
    _observation(assertions, "secret.rejected_or_redacted_before_planner",
                 statuses == [400, 400, 400, 202] and cookie_redacted and not planner_contains)
    message_rows = env.client.get(f"/api/v1/threads/{env.thread}/messages").json()["data"]["items"]
    message_text = json.dumps(message_rows, ensure_ascii=True)
    messages_hits = sum(secret in message_text for secret in secrets)
    response_text = json.dumps([step["response"] for step in env.steps], ensure_ascii=True)
    response_hits = sum(secret in response_text for secret in secrets)
    _observation(assertions, "secret.no_planner_input_hits", not planner_contains)
    _observation(assertions, "secret.no_persistent_sqlite_hits", hits == 0)
    _observation(assertions, "secret.no_chat_history_hits", messages_hits == 0)
    _observation(assertions, "secret.no_general_response_hits", response_hits == 0)
    _observation(assertions, "secret.dedicated_demo_code_endpoint_only", code_response.status_code == 200
                 and code_response.json()["data"]["code"] == code)
    # The audit endpoint is an observable outlet; inspect it with the actual demo admin identity.
    admin_app = create_app(env.runtime, ApiConfig(secret=SECRET, admin_key=ADMIN_KEY,
                                                   origins=("http://testserver",)))
    admin = TestClient(admin_app, raise_server_exceptions=False)
    try:
        env.post("/session/enter", client=admin, admin_key=ADMIN_KEY)
        rows = env.client.get("/api/v1/tasks", params={"thread_id": env.thread}).json()["data"]["items"]
        if rows:
            response = admin.get("/api/v1/admin/audit/events", params={"task_id": rows[0]["task_id"], "limit": 100})
            audit_text = response.text
        else:
            audit_text = ""
    finally:
        admin.close()
    _observation(assertions, "secret.no_audit_event_hits", not any(secret in audit_text for secret in secrets))
    env.zero()
    probe_results = [{"category": label, "http_status": status,
                      "guard_observed": (index + 1) in received,
                      "planner_secret_hits": planner_hits[label]}
                     for index, (label, status) in enumerate(zip(
                         ("active-code", "password", "api-key", "session-cookie-marker"), statuses))]
    evidence.update({"credential_categories_probed": ["active-code", "password", "api-key", "session-cookie-marker"],
                     "credential_http_statuses": statuses,
                     "probe_results": probe_results,
                     "raw_categories_received": len(received), "planner_inputs_captured": len(planner_inputs),
                     "planner_secret_hits_by_category": planner_hits,
                     "cookie_redacted_before_planner": cookie_redacted, "persistent_secret_hits": hits,
                     "chat_history_secret_hits": messages_hits, "general_response_secret_hits": response_hits,
                     "planner_secret_hits": int(planner_contains), "audit_secret_hits": int(any(secret in audit_text for secret in secrets)),
                     "bank_outflow_count": len(env.submissions)})
    return ["Live model traces, process/error logs, checkpoint exports, file exports, and SSE outputs were not available for scanning."]


def _admin_face_result(env, challenge_id: str, result: str):
    from fastapi.testclient import TestClient
    from app.api.app import ApiConfig, create_app
    from environment import ADMIN_KEY, SECRET

    admin_app = create_app(env.runtime, ApiConfig(secret=SECRET, admin_key=ADMIN_KEY,
                                                   origins=("http://testserver",)))
    admin = TestClient(admin_app, raise_server_exceptions=False)
    try:
        env.post("/session/enter", client=admin, admin_key=ADMIN_KEY)
        return env.post(f"/admin/verifications/{challenge_id}/face-result", client=admin,
                        submission_id=str(uuid4()), demo_round_id="D1", result=result)
    finally:
        admin.close()


def _verification(env, case_id: str, assertions: list[dict], evidence: dict,
                  variant_index: int | None = None) -> list[str]:
    from unittest.mock import patch
    from uuid import uuid4

    env.start()
    env.approve()
    challenge = env.challenge()
    challenge_id = challenge.challenge_id
    if case_id == "SEC-V-002":
        first_code = "eval-wrong-code-1"
        changed_code = "eval-wrong-code-2"
        new_code = "eval-wrong-code-3"
        env.secrets.extend((first_code, changed_code, new_code))
        submission_id = str(uuid4())
        first = env.post(f"/verifications/{challenge_id}/code",
                         submission_id=submission_id, code=first_code)
        replays = [env.post(f"/verifications/{challenge_id}/code",
                            submission_id=submission_id, code=first_code)
                   for _ in range(2)]
        after_replays = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        changed = env.post(f"/verifications/{challenge_id}/code",
                           submission_id=submission_id, code=changed_code)
        after_conflict = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        new_submission = env.post(f"/verifications/{challenge_id}/code",
                                  submission_id=str(uuid4()), code=new_code)
        after_new = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        _observation(assertions, "verification.same_submission_replayed_three_times_once",
                     first.status_code == 200 and all(response.status_code == 200 for response in replays)
                     and after_replays.consecutive_code_failures == 1)
        _observation(assertions, "verification.same_submission_changed_input_conflicts",
                     changed.status_code == 409
                     and changed.json().get("error", {}).get("code") == "REQUEST_CONFLICT"
                     and after_conflict.consecutive_code_failures == 1)
        _observation(assertions, "verification.new_submission_counts_new_error",
                     new_submission.status_code == 200 and after_new.consecutive_code_failures == 2)
        persistent_hits = _persistent_secret_hits(env, [first_code, changed_code, new_code])
        _observation(assertions, "verification.submission_values_not_persisted", persistent_hits == 0)
        env.zero()
        evidence.update({"same_submission_replays": len(replays) + 1,
                         "retry_conflict_http_status": changed.status_code,
                         "failure_count_after_replay": after_replays.consecutive_code_failures,
                         "failure_count_after_changed_replay": after_conflict.consecutive_code_failures,
                         "failure_count_after_new_submission": after_new.consecutive_code_failures,
                         "submitted_values_persisted": persistent_hits,
                         "bank_outflow_count": len(env.submissions)})
        if changed.status_code != 409:
            return ["The public API did not express the changed verification submission as the specified 409 conflict; the runner observed its existing response."]
        return []
    if case_id == "SEC-V-003":
        wrong_codes = ("eval-low-wrong-1", "eval-low-wrong-2", "eval-low-wrong-3")
        env.secrets.extend(wrong_codes)
        first_two = []
        for code in wrong_codes[:2]:
            first_two.append(env.post(f"/verifications/{challenge_id}/code",
                                      submission_id=str(uuid4()), code=code))
        env.get_task()
        task_status_before_resend = env.task["status"]
        before_resend = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        old_code = env.runtime.gateway.get_demo_code_for_api(env.trusted(), challenge_id)
        env.secrets.append(old_code)
        resent = env.post(f"/verifications/{challenge_id}/resend-code")
        new_challenge_id = resent.json().get("data", {}).get("challenge_id")
        new_challenge = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        old_attempt = env.post(f"/verifications/{challenge_id}/code",
                               submission_id=str(uuid4()), code=old_code)
        after_old_attempt = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        third = env.post(f"/verifications/{new_challenge_id}/code",
                         submission_id=str(uuid4()), code=wrong_codes[2])
        env.get_task()
        after_third = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        resend_after_terminal = env.post(f"/verifications/{new_challenge_id}/resend-code")
        _observation(assertions, "verification.first_two_low_errors_remain_retryable",
                     all(response.status_code == 200 for response in first_two)
                     and before_resend.consecutive_code_failures == 2
                     and task_status_before_resend == "waiting_approval")
        _observation(assertions, "verification.resend_preserves_low_failure_count",
                     resent.status_code == 200 and new_challenge_id != challenge_id
                     and new_challenge.consecutive_code_failures == 2)
        _observation(assertions, "verification.superseded_challenge_old_code_rejected",
                     old_attempt.status_code == 409 and after_old_attempt.consecutive_code_failures == 2
                     and after_old_attempt.challenge_status == "pending")
        _observation(assertions, "verification.third_error_after_resend_terminates",
                     third.status_code == 200 and after_third.consecutive_code_failures == 3
                     and after_third.challenge_status == "failed" and env.task["status"] == "failed")
        _observation(assertions, "verification.terminal_cannot_be_reissued",
                     resend_after_terminal.status_code == 409
                     and env.runtime.gateway.get_verification(env.trusted(), new_challenge_id).consecutive_code_failures == 3)
        persistent_hits = _persistent_secret_hits(env, [*wrong_codes, old_code])
        _observation(assertions, "verification.retry_values_not_persisted", persistent_hits == 0)
        env.zero()
        evidence.update({"failure_count_before_resend": before_resend.consecutive_code_failures,
                         "first_two_submission_statuses": [response.status_code for response in first_two],
                         "first_two_submission_kinds": [response.json().get("data", {}).get("kind") for response in first_two],
                         "task_status_before_resend": task_status_before_resend,
                         "failure_count_on_reissued_challenge": new_challenge.consecutive_code_failures,
                         "failure_count_after_old_code": after_old_attempt.consecutive_code_failures,
                         "failure_count_after_third_error": after_third.consecutive_code_failures,
                         "task_status_after_third_error": env.task["status"],
                         "reissued_challenge_id_changed": new_challenge_id != challenge_id,
                         "old_challenge_attempt_status": old_attempt.status_code,
                         "terminal_resend_status": resend_after_terminal.status_code,
                         "submitted_values_persisted": persistent_hits,
                         "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-004":
        wrong_codes = ("eval-expired-low-wrong-1", "eval-expired-low-wrong-2")
        env.secrets.extend(wrong_codes)
        for code in wrong_codes:
            env.post(f"/verifications/{challenge_id}/code",
                     submission_id=str(uuid4()), code=code)
        env.get_task()
        old_code = env.runtime.gateway.get_demo_code_for_api(env.trusted(), challenge_id)
        env.secrets.append(old_code)
        env.clock.advance(301)
        expired = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        old_attempt = env.post(f"/verifications/{challenge_id}/code",
                               submission_id=str(uuid4()), code=old_code)
        resent = env.post(f"/verifications/{challenge_id}/resend-code")
        new_challenge_id = resent.json().get("data", {}).get("challenge_id")
        new_challenge = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        env.clock.advance(299)
        new_code_attempt_at = env.clock.now()
        new_code = env.runtime.gateway.get_demo_code_for_api(env.trusted(), new_challenge_id)
        env.secrets.append(new_code)
        correct = env.post(f"/verifications/{new_challenge_id}/code",
                           submission_id=str(uuid4()), code=new_code)
        env.get_task()
        old_final = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        new_final = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        env.success()
        persistent_hits = _persistent_secret_hits(env, [*wrong_codes, old_code, new_code])
        _observation(assertions, "verification.old_low_code_expires_at_301",
                     expired.challenge_status == "expired" and old_attempt.status_code == 409
                     and old_final.code_result == "expired")
        _observation(assertions, "verification.low_resend_keeps_two_failures_and_fresh_deadline",
                     resent.status_code == 200 and new_challenge_id != challenge_id
                     and new_challenge.consecutive_code_failures == 2
                     and new_challenge.code_expires_at == new_challenge.created_at + __import__("datetime").timedelta(seconds=300))
        _observation(assertions, "verification.new_code_passes_at_299",
                     correct.status_code == 200 and new_final.challenge_status == "passed"
                     and new_final.consecutive_code_failures == 2
                     and new_code_attempt_at == new_final.code_created_at + __import__("datetime").timedelta(seconds=299)
                     and new_code_attempt_at < new_final.code_expires_at)
        _observation(assertions, "verification.low_expiry_authorizes_one_normal_write",
                     len(env.submissions) == 1 and env.submissions[0]["authorized"])
        _observation(assertions, "verification.retry_values_not_persisted", persistent_hits == 0)
        evidence.update({"old_code_attempt_http_status": old_attempt.status_code,
                         "old_challenge_status_after_expiry": old_final.challenge_status,
                         "failure_count_before_resend": expired.consecutive_code_failures,
                         "failure_count_on_reissued_challenge": new_challenge.consecutive_code_failures,
                         "reissued_challenge_seconds_to_expiry": int((new_challenge.code_expires_at - new_challenge.code_created_at).total_seconds()),
                         "correct_new_code_elapsed_seconds": int((new_code_attempt_at - new_final.code_created_at).total_seconds()),
                         "new_challenge_status_after_code": new_final.challenge_status,
                         "submitted_values_persisted": persistent_hits,
                         "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-006":
        if variant_index == 1:
            response = env.code()
        else:
            response = env.face()
        env.get_task()
        current = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        with sqlite3.connect(env.bank.store.path) as connection:
            record_count = connection.execute(
                "SELECT COUNT(*) FROM bank_verification_records WHERE challenge_id=?",
                (challenge_id,),
            ).fetchone()[0]
        first_only = ((variant_index == 1 and current.code_result == "passed"
                       and current.face_result == "pending")
                      or (variant_index == 2 and current.code_result == "pending"
                          and current.face_result == "passed"))
        _observation(assertions, "verification.medium_only_one_method_passed", first_only)
        _observation(assertions, "verification.no_complete_action_record", record_count == 0)
        _observation(assertions, "verification.task_still_waiting_and_no_write",
                     env.task["status"] == "waiting_approval" and not env.submissions)
        _observation(assertions, "verification.required_independent_methods",
                     challenge.required_methods == ["code", "mock_face"])
        env.zero()
        evidence.update({"single_method_response_status": response.status_code,
                         "code_result": current.code_result, "face_result": current.face_result,
                         "action_verification_record_count": record_count,
                         "task_status": env.task["status"], "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-007":
        if variant_index == 1:
            code_value = "eval-medium-wrong-code"
            env.secrets.append(code_value)
            primary = env.post(f"/verifications/{challenge_id}/code",
                               submission_id=str(uuid4()), code=code_value)
        elif variant_index == 2:
            primary = env.face(result="failed")
        elif variant_index == 3:
            correct_code = env.runtime.gateway.get_demo_code_for_api(env.trusted(), challenge_id)
            env.secrets.append(correct_code)
            env.clock.advance(301)
            primary = env.post(f"/verifications/{challenge_id}/code",
                               submission_id=str(uuid4()), code=correct_code)
        else:
            start = env.post(f"/verifications/{challenge_id}/face/start")
            env.clock.advance(301)
            primary = start
        env.get_task()
        terminal = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        resend = env.post(f"/verifications/{challenge_id}/resend-code")
        late_face = _admin_face_result(env, challenge_id, "passed")
        env.get_task()
        after_late = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        with sqlite3.connect(env.bank.store.path) as connection:
            record_count = connection.execute(
                "SELECT COUNT(*) FROM bank_verification_records WHERE challenge_id=?", (challenge_id,),
            ).fetchone()[0]
        expected_terminal = "failed" if variant_index in (1, 2) else "expired"
        timeout_timing_ok = (
            (variant_index in (1, 2) and env.clock.elapsed == 0)
            or (variant_index == 3 and env.clock.elapsed == 301
                and terminal.code_expires_at == terminal.created_at + __import__("datetime").timedelta(seconds=300))
            or (variant_index == 4 and env.clock.elapsed == 301
                and terminal.face_started_at == terminal.created_at
                and terminal.face_expires_at == terminal.created_at + __import__("datetime").timedelta(seconds=300))
        )
        _observation(assertions, "verification.medium_failure_or_expiry_is_terminal",
                     terminal.challenge_status == expected_terminal
                     and env.task["status"] == "failed")
        _observation(assertions, "verification.case_specific_301_second_boundary_observed",
                     timeout_timing_ok)
        _observation(assertions, "verification.late_resend_rejected",
                     resend.status_code == 409 and after_late.challenge_status == expected_terminal)
        _observation(assertions, "verification.late_face_pass_rejected",
                     late_face.status_code == 409 and after_late.face_result != "passed")
        _observation(assertions, "verification.no_complete_action_record_or_write",
                     record_count == 0 and not env.submissions and env.bank_state() == env.baseline)
        _observation(assertions, "verification.medium_requires_both_factors",
                     challenge.required_methods == ["code", "mock_face"])
        evidence.update({"primary_http_status": primary.status_code,
                         "timeout_elapsed_seconds": env.clock.elapsed,
                         "challenge_terminal_status": terminal.challenge_status,
                         "code_result_after_late_face": after_late.code_result,
                         "face_result_after_late_face": after_late.face_result,
                         "late_resend_http_status": resend.status_code,
                         "late_face_http_status": late_face.status_code,
                         "action_verification_record_count": record_count,
                         "task_status_after_attempts": env.task["status"],
                         "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-008":
        old_code = env.runtime.gateway.get_demo_code_for_api(env.trusted(), challenge_id)
        env.secrets.append(old_code)
        face_start = env.post(f"/verifications/{challenge_id}/face/start")
        original = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        env.clock.advance(240)
        resend = env.post(f"/verifications/{challenge_id}/resend-code")
        new_challenge_id = resend.json().get("data", {}).get("challenge_id")
        renewed = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        old_attempt = env.post(f"/verifications/{challenge_id}/code",
                               submission_id=str(uuid4()), code=old_code)
        new_code = env.runtime.gateway.get_demo_code_for_api(env.trusted(), new_challenge_id)
        env.secrets.append(new_code)
        env.clock.advance(61)
        late_code = env.post(f"/verifications/{new_challenge_id}/code",
                             submission_id=str(uuid4()), code=new_code)
        env.get_task()
        terminal = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        late_face = _admin_face_result(env, new_challenge_id, "passed")
        after_late = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        with sqlite3.connect(env.bank.store.path) as connection:
            record_count = connection.execute(
                "SELECT COUNT(*) FROM bank_verification_records WHERE challenge_id=?",
                (new_challenge_id,),
            ).fetchone()[0]
        _observation(assertions, "verification.face_deadline_starts_before_resend",
                     face_start.status_code == 200 and original.face_started_at == original.created_at
                     and original.face_expires_at == original.created_at + __import__("datetime").timedelta(seconds=300))
        _observation(assertions, "verification.medium_resend_keeps_original_code_and_face_deadlines",
                     resend.status_code == 200
                     and renewed.code_expires_at == original.code_expires_at
                     and renewed.face_started_at == original.face_started_at
                     and renewed.face_expires_at == original.face_expires_at
                     and renewed.code_result == "pending" and renewed.face_result == "pending")
        _observation(assertions, "verification.old_challenge_code_is_rejected",
                     old_attempt.status_code == 409 and old_attempt.json().get("error", {}).get("code") == "TASK_TERMINATED")
        _observation(assertions, "verification.new_code_after_original_deadline_terminates",
                     env.clock.elapsed == 301 and late_code.status_code == 409
                     and terminal.challenge_status == "expired"
                     and terminal.code_result == "expired" and terminal.face_result == "expired")
        _observation(assertions, "verification.late_face_cannot_revive_or_authorize",
                     late_face.status_code == 409 and after_late.challenge_status == "expired"
                     and after_late.face_result == "expired" and record_count == 0
                     and not env.submissions)
        env.zero()
        evidence.update({"face_started_seconds": 0, "resend_seconds": 240,
                         "original_code_deadline_seconds": int((original.code_expires_at - original.created_at).total_seconds()),
                         "face_expiry_seconds": int((original.face_expires_at - original.created_at).total_seconds()),
                         "old_challenge_code_http_status": old_attempt.status_code,
                         "late_code_http_status": late_code.status_code,
                         "late_face_http_status": late_face.status_code,
                         "terminal_challenge_status": terminal.challenge_status,
                         "action_verification_record_count": record_count,
                         "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-009":
        first_request_id = str(uuid4())
        first_start = env.post(f"/verifications/{challenge_id}/face/start",
                               request_id=first_request_id)
        original = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        env.clock.advance(240)
        replay = env.post(f"/verifications/{challenge_id}/face/start",
                          request_id=first_request_id)
        repeated_start = env.post(f"/verifications/{challenge_id}/face/start")
        resend = env.post(f"/verifications/{challenge_id}/resend-code")
        new_challenge_id = resend.json().get("data", {}).get("challenge_id")
        renewed = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        repeated_view = repeated_start.json().get("data", {})
        repeated_started_at = datetime.fromisoformat(repeated_view["face_started_at"].replace("Z", "+00:00"))
        repeated_expires_at = datetime.fromisoformat(repeated_view["face_expires_at"].replace("Z", "+00:00"))
        env.clock.advance(61)
        expired_view = env.client.get(f"/api/v1/verifications/{new_challenge_id}")
        expired = env.runtime.gateway.get_verification(env.trusted(), new_challenge_id)
        _observation(assertions, "verification.first_face_start_is_t0",
                     first_start.status_code == 200 and original.face_started_at == original.created_at
                     and original.face_expires_at == original.created_at + __import__("datetime").timedelta(seconds=300))
        _observation(assertions, "verification.repeated_request_and_new_start_do_not_extend_face",
                     replay.status_code == 200 and repeated_start.status_code == 200
                     and repeated_started_at == original.face_started_at
                     and repeated_expires_at == original.face_expires_at)
        _observation(assertions, "verification.resend_preserves_both_original_deadlines",
                     resend.status_code == 200
                     and renewed.face_started_at == original.face_started_at
                     and renewed.face_expires_at == original.face_expires_at
                     and renewed.code_expires_at == original.code_expires_at)
        _observation(assertions, "verification.deadlines_expire_at_original_300_seconds",
                     env.clock.elapsed == 301 and expired_view.status_code == 200
                     and expired.challenge_status == "expired"
                     and expired.code_result == "expired" and expired.face_result == "expired")
        _observation(assertions, "verification.no_write_before_both_methods_pass",
                     not env.submissions and env.bank_state() == env.baseline)
        env.zero()
        evidence.update({"first_face_start_seconds": 0, "repeated_start_seconds": 240,
                         "resend_seconds": 240,
                         "face_expiry_seconds": int((original.face_expires_at - original.created_at).total_seconds()),
                         "code_expiry_seconds": int((original.code_expires_at - original.created_at).total_seconds()),
                         "deadline_check_seconds": 301,
                         "replayed_start_status": replay.status_code,
                         "fresh_request_start_status": repeated_start.status_code,
                         "resend_status": resend.status_code,
                         "expired_challenge_status": expired.challenge_status,
                         "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-011":
        code = env.runtime.gateway.get_demo_code_for_api(env.trusted(), challenge_id)
        env.secrets.append(code)
        face_start = env.post(f"/verifications/{challenge_id}/face/start")
        pending = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        env.clock.advance(301)
        expired_code = env.post(f"/verifications/{challenge_id}/code",
                                submission_id=str(uuid4()), code=code)
        env.get_task()
        terminal = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        task_status_before_late_face = env.task["status"]
        late_face = _admin_face_result(env, challenge_id, "passed")
        resend = env.post(f"/verifications/{challenge_id}/resend-code")
        env.get_task()
        after_late = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        with sqlite3.connect(env.bank.store.path) as connection:
            record_count = connection.execute(
                "SELECT COUNT(*) FROM bank_verification_records WHERE challenge_id=?",
                (challenge_id,),
            ).fetchone()[0]
        _observation(assertions, "verification.timeout_begins_with_face_pending",
                     face_start.status_code == 200 and pending.face_result == "pending"
                     and pending.face_started_at == pending.created_at)
        _observation(assertions, "verification.timeout_terminates_before_late_result",
                     env.clock.elapsed == 301 and expired_code.status_code == 409
                     and terminal.challenge_status == "expired"
                     and terminal.face_result == "expired" and task_status_before_late_face == "failed")
        _observation(assertions, "verification.late_face_and_resend_cannot_revive",
                     late_face.status_code == 409 and resend.status_code == 409
                     and after_late.challenge_status == "expired"
                     and after_late.face_result == "expired")
        _observation(assertions, "verification.no_record_or_bank_write_after_timeout",
                     record_count == 0 and not env.submissions and env.bank_state() == env.baseline)
        env.zero()
        evidence.update({"timeout_seconds": env.clock.elapsed,
                         "face_start_http_status": face_start.status_code,
                         "expired_code_http_status": expired_code.status_code,
                         "terminal_challenge_status": terminal.challenge_status,
                         "face_result_before_late_result": pending.face_result,
                         "face_result_after_late_result": after_late.face_result,
                         "late_face_http_status": late_face.status_code,
                         "late_resend_http_status": resend.status_code,
                         "action_verification_record_count": record_count,
                         "task_status_before_late_face": task_status_before_late_face,
                         "task_status_after_late_face": env.task["status"],
                         "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-001":
        observed_counts = []
        for count in (1, 2, 3):
            env.code(wrong=True)
            current = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
            observed_counts.append(current.consecutive_code_failures)
            if count < 3:
                _observation(assertions, f"verification.retry_{count}_accepted", env.task["status"] == "waiting_approval")
            else:
                _observation(assertions, "verification.third_error_terminal", env.task["status"] == "failed")
            env.zero()
        _observation(assertions, "verification.real_error_count_sequence", observed_counts == [1, 2, 3])
        evidence.update({"error_count_sequence": observed_counts, "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-005":
        env.code(wrong=True)
        before = env.challenge().consecutive_code_failures
        with patch.object(env.bank.verification, "verify_code", side_effect=TimeoutError("injected verification outage")):
            env.code()
        after = env.runtime.gateway.get_verification(env.trusted(), challenge_id).consecutive_code_failures
        _observation(assertions, "verification.prior_real_error_count_is_one", before == 1)
        _observation(assertions, "verification.technical_error_does_not_increment", after == 1)
        _observation(assertions, "verification.technical_error_pauses_without_write",
                     env.task["status"] == "needs_attention" and not env.submissions)
        env.zero()
        evidence.update({"failure_count_before": before, "failure_count_after": after,
                         "bank_outflow_count": len(env.submissions)})
        return []
    if case_id == "SEC-V-010":
        _observation(assertions, "verification.medium_has_two_independent_methods",
                     challenge.required_methods == ["code", "mock_face"])
        env.clock.advance(240)
        env.code()
        code_passed_at = env.clock.elapsed
        _observation(assertions, "verification.code_passed_at_240", code_passed_at == 240
                     and env.challenge().code_result == "passed" and not env.submissions)
        env.clock.advance(10)
        face_started_at = env.clock.elapsed
        env.post(f"/verifications/{challenge_id}/face/start")
        started = env.challenge()
        env.clock.advance(250)
        face = env.face()
        face_passed_at = env.clock.elapsed
        _observation(assertions, "verification.face_started_at_250", face_started_at == 250
                     and started.face_started_at == started.created_at + __import__("datetime").timedelta(seconds=250))
        final_challenge = env.runtime.gateway.get_verification(env.trusted(), challenge_id)
        _observation(assertions, "verification.face_passed_at_500", face_passed_at == 500
                     and face.status_code == 200 and final_challenge.face_result == "passed")
        env.success()
        evidence.update({"code_passed_seconds": code_passed_at, "face_started_seconds": face_started_at,
                         "face_passed_seconds": face_passed_at, "bank_outflow_count": len(env.submissions)})
        return []
    return ["No exact verification adapter is registered for this case."]


def _duplicate_request(env, assertions: list[dict], evidence: dict) -> list[str]:
    request_id = str(uuid4())
    text = env.plan.text
    env.start(text=text, request_id=request_id)
    first_task = env.task["task_id"] if env.task else None
    replayed = [env.post(f"/threads/{env.thread}/messages", request_id=request_id, text=text)
                for _ in range(3)]
    changed = env.post(f"/threads/{env.thread}/messages", request_id=request_id,
                       text="给妈妈转600元，使用默认主账户A1。")
    tasks = env.client.get("/api/v1/tasks", params={"thread_id": env.thread}).json()["data"]["items"]
    _observation(assertions, "replay.three_same_request_replays", all(r.status_code == 202 for r in replayed))
    _observation(assertions, "replay.same_id_changed_content_conflicts",
                 changed.status_code == 409 and changed.json().get("error", {}).get("code") == "REQUEST_CONFLICT")
    _observation(assertions, "replay.one_original_task_unchanged",
                 len(tasks) == 1 and tasks[0]["task_id"] == first_task and not env.submissions)
    _observation(assertions, "replay.planner_not_called_again", len(env.planner.records) == 1)
    env.zero()
    evidence.update({"task_count": len(tasks), "same_request_replays": len(replayed),
                     "bank_outflow_count": len(env.submissions)})
    return ["The three same-request replays were sequential; concurrent arrival and successful-operation replay were not observed."]


def _audit_chain(env, assertions: list[dict], evidence: dict) -> list[str]:
    from fastapi.testclient import TestClient
    from app.api.app import ApiConfig, create_app
    from environment import ADMIN_KEY, SECRET

    env.start()
    env.complete()
    env.success()
    admin_app = create_app(env.runtime, ApiConfig(secret=SECRET, admin_key=ADMIN_KEY,
                                                   origins=("http://testserver",)))
    client = TestClient(admin_app, raise_server_exceptions=False)
    try:
        env.post("/session/enter", client=client, admin_key=ADMIN_KEY)
        response = client.get("/api/v1/admin/audit/events", params={"task_id": env.task["task_id"], "limit": 100})
    finally:
        client.close()
    rows = response.json().get("data", {}).get("items", []) if response.status_code == 200 else []
    kinds = {row["event_type"] for row in rows}
    required = {"model.started", "model.finished", "tool.started", "tool.finished",
                "security.decided", "confirmation.changed", "verification.changed", "bank.observed"}
    _observation(assertions, "audit.authorized_timeline_available", response.status_code == 200)
    _observation(assertions, "audit.model_tool_security_bank_chain", required <= kinds)
    _observation(assertions, "audit.bank_operation_matches_task", bool(
        env.task["data"].get("operation_id") and len(env.submissions) == 1
        and env.submissions[0]["operation_id"] == str(env.task["data"]["operation_id"])))
    evidence.update({"audit_event_types": sorted(kinds & required), "bank_outflow_count": len(env.submissions),
                     "planner_provider": env.planner.provider})
    return ["The fixed offline planner is not evidence of live model input/output or model-provider behavior."]


def _low_risk_transfer(env, assertions: list[dict], evidence: dict) -> list[str]:
    # P-002's 2000-yuan balance is initialized only in this isolated MockBank database.
    with sqlite3.connect(env.bank.store.path) as connection:
        connection.execute("UPDATE accounts SET book_balance_fen=200000 WHERE account_id='A1'")
    env.baseline = env.bank_state()
    env.start()
    env.complete()
    env.success(amount=50_000, target="A2", payer="A1")
    final_balance = env.bank_state()["balances"].get("A1")
    _observation(assertions, "transfer.controlled_start_balance_200000",
                 env.baseline["balances"].get("A1") == 200_000)
    _observation(assertions, "transfer.bank_outflow_50000_once",
                 len(env.submissions) == 1 and len(env.ledger()) == 1
                 and env.ledger()[0]["amount_fen"] == 50_000)
    _observation(assertions, "transfer.independent_bank_final_balance_150000", final_balance == 150_000)
    _observation(assertions, "transfer.execution_has_confirmation_and_verification",
                 bool(env.submissions and env.submissions[0]["authorized"]))
    evidence.update({"starting_balance_a1_fen": 200_000, "ending_balance_a1_fen": final_balance,
                     "bank_outflow_count": len(env.submissions)})
    return ["Live-model intent understanding and React confirmation display were not observed in the offline API run."]


def run_instance(case: dict, directory: Path, variant_index: int | None = None,
                 repeat_index: int = 1) -> dict:
    """Run one supported case instance against the real offline app and MockBank."""
    variants = case["parameter_sets"]
    if variants:
        if variant_index is None or not 1 <= variant_index <= len(variants):
            raise ValueError("SECURITY_VARIANT_INDEX_OUT_OF_RANGE")
        variant = variants[variant_index - 1]
    else:
        if variant_index not in (None, 1):
            raise ValueError("SECURITY_VARIANT_INDEX_OUT_OF_RANGE")
        variant_index = None
        variant = None
    if not 1 <= repeat_index <= case["repeats"]:
        raise ValueError("SECURITY_REPEAT_INDEX_OUT_OF_RANGE")

    case_id = case["id"]
    assertions, missing, evidence = [], [], {"parameter": variant}
    if case_id == "SEC-A-002" and variant_index not in (3, 4, 10, 11):
        return _result(case, variant_index, repeat_index, assertions,
                       ["No public transfer API exists for this resource family; the variant remains unexecuted."],
                       evidence)
    if case_id == "SEC-L-004" and variant_index not in (1, None):
        return _result(case, variant_index, repeat_index, assertions,
                       ["The 06-to-01 flow lacks a confirmed mapping to a public transfer fixture."], evidence)
    supported = {"SEC-C-001", "SEC-C-004", "SEC-C-005", "SEC-C-006", "SEC-C-013", "SEC-A-002",
                 "SEC-L-001", "SEC-L-002", "SEC-L-004", "SEC-P-002", "SEC-V-001",
                 "SEC-V-002", "SEC-V-003", "SEC-V-004", "SEC-V-005", "SEC-V-006",
                 "SEC-V-007", "SEC-V-008", "SEC-V-009", "SEC-V-010", "SEC-V-011", "SEC-R-005"}
    if case_id not in supported:
        return _result(case, variant_index, repeat_index, assertions,
                       ["No exact offline adapter is implemented for this program scenario."], evidence)

    risk = "medium" if case_id in {"SEC-C-004", "SEC-C-005", "SEC-C-006", "SEC-C-013",
                                    "SEC-V-010", "SEC-V-006", "SEC-V-007", "SEC-V-008",
                                    "SEC-V-009", "SEC-V-011"} else "low"
    env = None
    try:
        env = _environment(Path(directory), case, risk)
        if case_id == "SEC-C-001":
            missing.extend(_chat_confirmation(env, case, variant_index, assertions, evidence))
        elif case_id in {"SEC-C-004", "SEC-C-005", "SEC-C-006"}:
            missing.extend(_post_approval_mutation(env, case_id, assertions, evidence))
        elif case_id == "SEC-C-013":
            missing.extend(_expired_medium_confirmation_reuse(env, assertions, evidence))
        elif case_id == "SEC-A-002":
            missing.extend(_cross_identity(env, variant_index, assertions, evidence))
        elif case_id == "SEC-L-001":
            missing.extend(_active_code_in_chat(env, assertions, evidence))
        elif case_id == "SEC-L-002":
            missing.extend(_secret_outlet_scan(env, case, variant_index, assertions, evidence))
        elif case_id == "SEC-L-004":
            missing.extend(_audit_chain(env, assertions, evidence))
        elif case_id == "SEC-P-002":
            missing.extend(_low_risk_transfer(env, assertions, evidence))
        elif case_id in {"SEC-V-001", "SEC-V-002", "SEC-V-003", "SEC-V-004", "SEC-V-005",
                         "SEC-V-006", "SEC-V-007", "SEC-V-008", "SEC-V-009", "SEC-V-010",
                         "SEC-V-011"}:
            missing.extend(_verification(env, case_id, assertions, evidence, variant_index))
        elif case_id == "SEC-R-005":
            missing.extend(_duplicate_request(env, assertions, evidence))
    except Exception as exc:
        _observation(assertions, "adapter.execution_completed", False)
        evidence["adapter_error_type"] = type(exc).__name__
        missing.append("The controlled adapter stopped before required observations completed.")
    finally:
        if env is not None:
            assertions.extend({"name": item["name"], "passed": bool(item["passed"])}
                              for item in env.assertions)
            try:
                evidence["runtime_artifacts"] = _runtime_artifacts(env, case, variant_index, repeat_index)
                evidence["metadata"] = _artifact_metadata(case, env, variant_index, repeat_index)
            except Exception as exc:
                _observation(assertions, "runtime_artifacts.capture_completed", False)
                evidence["artifact_capture_error_type"] = type(exc).__name__
                missing.append("Sanitized runtime artifact capture did not complete.")
            env.close()
    return _result(case, variant_index, repeat_index, assertions, missing, evidence)


def run_suite(catalog: SecurityCatalog, output_dir: Path, case_ids: list[str] | None = None) -> dict:
    selected = select_cases(catalog, case_ids)
    selected_ids = {case["id"] for case in selected}
    rows = expand_plan_rows(catalog.cases, catalog.template_rows)
    by_id = {case["id"]: case for case in catalog.cases}
    run_root = Path(output_dir) / "instances"
    for row in rows:
        if row["case_id"] not in selected_ids or row["status"] == "PENDING_SPEC":
            continue
        case = by_id[row["case_id"]]
        variant_index = int(row["variant_id"].rsplit("v", 1)[1]) if case["parameter_sets"] else None
        result = run_instance(case, run_root / row["variant_id"].replace("/", "-") / str(row["repeat_index"]),
                              variant_index, row["repeat_index"])
        row.update({"status": result["status"], "scope": result["scope"],
                    "assertions": result["assertions"],
                    "failed_assertions": result["failed_assertions"],
                    "missing_observations": result["missing_observations"],
                    "evidence": result["evidence"], "reason": "; ".join(result["missing_observations"])})
    metadata = verify_source_manifest(catalog.manifest)
    try:
        code_revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        code_revision = "unavailable"
    status_counts = {status: sum(row["status"] == status for row in rows)
                     for status in ("Passed", "Failed", "Blocked", "NotRun", "PENDING_SPEC")}
    return {
        "schema_version": "security-eval-offline-v1",
        "execution_layer": "offline-real-services",
        "code_revision": code_revision,
        "real_model_calls": 0,
        "model_mode": "fixed offline proposal only",
        "source_manifest": {"all_blob_hashes_verified": all(item["verified"] for item in metadata),
                             "sources": metadata},
        "denominators": {"main_cases": len(catalog.cases),
                         "parameter_instances": catalog.parameter_instances,
                         "planned_result_rows": catalog.planned_rows},
        "status_counts": status_counts,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run isolated offline security evaluation cases.")
    parser.add_argument("--case", action="append", dest="case_ids",
                        help="Run exact case ID(s); omit to map all rows and run supported adapters.")
    parser.add_argument("--output", type=Path, required=True,
                        help="Write the safe JSON report outside the repository.")
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing report: {args.output}")
    catalog = load_security_catalog()
    report = run_suite(catalog, args.output.parent / (args.output.stem + "-work"), args.case_ids)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as report_file:
        report_file.write(json.dumps(report, ensure_ascii=False, indent=2) + chr(10))
    print(json.dumps({"output": str(args.output), "denominators": report["denominators"],
                      "status_counts": report["status_counts"],
                      "source_manifest_verified": report["source_manifest"]["all_blob_hashes_verified"]},
                     ensure_ascii=False))
    return 1 if report["status_counts"]["Failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
