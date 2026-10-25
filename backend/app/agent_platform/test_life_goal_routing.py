"""Issue301: prompt boundaries, unchanged dispatch and opt-in live routing.

Live cases only call understand(), never start a business capability. Scripted
tests verify the program handoff; they do not measure model understanding.
"""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from time import monotonic
from unittest.mock import patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.contracts.platform import TrustedContext
from app.storage.database import connect

from .local_demo import build_runtime, load_config
from .model import ReplyOnly, TransferProposal
from .test_local_demo import ConnectorTestModel, configuration


CROSS = "cross.start_task"
CANCEL = "subscription.cancel_subscription"
LIST = "subscription.list_subscriptions"
TRANSFER = "transfer.start_transfer"


class RecordingModel(ConnectorTestModel):
    selected: str = CROSS
    prompts: list[str] = Field(default_factory=list)

    def _generate(self, messages, **kwargs):
        self.prompts.append(str(messages[0].content))
        message = AIMessage(content="", tool_calls=[{
            "name": "propose_transfer", "args": {"capability_name": self.selected},
            "id": "selected", "type": "tool_call",
        }])
        return ChatResult(generations=[ChatGeneration(message=message)])


def owner(runtime, demo_round_id="D1", user_id="U1"):
    now = datetime.now(timezone.utc)
    runtime.application.create_session(
        "routing-session", user_id, demo_round_id, now.isoformat(),
        (now + timedelta(days=1)).isoformat(),
    )
    return TrustedContext(user_id=user_id, session_id="routing-session",
                          demo_round_id=demo_round_id,
                          task_id="routing-task", run_id="routing-run", parent_task_id=None)


def scripted_runtime(tmp_path, selected=CROSS):
    model = RecordingModel(selected=selected)
    with patch("app.agent_platform.local_demo.ChatOpenAI", return_value=model):
        runtime = build_runtime(configuration(tmp_path))
    return runtime, model, owner(runtime)


def test_full_goal_instruction_is_not_overridden_by_subscription_action_words(tmp_path):
    runtime, model, trusted = scripted_runtime(tmp_path)
    runtime.harness.understand(trusted, "最近钱怎么花得快，帮我处理不用的扣费")
    prompt = model.prompts[-1]
    # This former unconditional priority overrode the life-goal catalog.
    assert "盘点词与退订动作词同时出现时按退订处理" not in prompt
    assert "完整生活目标" in prompt and CROSS in prompt


def test_goal_route_is_not_offered_without_the_registered_cross_capability(tmp_path):
    runtime, model, trusted = scripted_runtime(tmp_path, CANCEL)
    catalog = [entry for entry in runtime.harness.registry.public_catalog() if entry["name"] != CROSS]
    runtime.harness.planner.select(
        "我想少花些钱", trusted, catalog, runtime.memory, "isolated-planning-thread",
    )
    assert CROSS not in model.prompts[-1]
    assert "完整生活目标" not in model.prompts[-1]
    assert CANCEL in model.prompts[-1]


@pytest.mark.parametrize("selected", [CROSS, CANCEL, LIST, TRANSFER])
def test_program_preserves_the_model_candidate_without_keyword_rerouting(tmp_path, selected):
    runtime, _, trusted = scripted_runtime(tmp_path, selected)
    text = "我想少花点钱，帮我处理不用的扣费"
    proposal = runtime.harness.understand(trusted, text)
    assert isinstance(proposal, TransferProposal)
    assert proposal.capability_name == selected
    assert runtime.application.list_session_tasks("U1", trusted.demo_round_id, trusted.session_id) == []


def test_recorded_wrong_candidate_replays_as_inventory_not_a_dispatch_error(tmp_path):
    # Replay PR300's actual model choice, not a stand-in for model understanding.
    runtime, _, trusted = scripted_runtime(tmp_path, CANCEL)
    text = "最近钱怎么花得快，帮我处理不用的扣费"
    result = runtime.harness.handle_message(trusted, uuid4(), text)
    task = runtime.application.get_task("U1", "D1", trusted.task_id)
    assert task.snapshot["capability_name"] == CANCEL
    assert result.status.value == "succeeded"
    assert runtime.application.list_child_tasks("U1", "D1", trusted.task_id) == []
    with closing(connect(runtime.gateway._bank.store.path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM bank_operations").fetchone()[0] == 0


LIVE_CASES = [
    ("original", "最近钱怎么花得快，帮我处理不用的扣费", CROSS),
    ("spend_reason", "这两个月开销越来越大，帮我查查原因，把我已经不用的服务整理一下再停掉。", CROSS),
    ("spend_plan", "每月还有哪些钱能省？看看账单和自动续费，帮我把不需要的处理好。", CROSS),
    ("spend_unused", "我想少花些冤枉钱，用不上的订阅别让它继续扣了，先给我看看怎么安排。", CROSS),
    ("single", "把优酷视频的自动续费关掉。", CANCEL),
    ("single_missing_field", "我想退掉一个自动续费。", CANCEL),
    ("single_with_goal", "钱有点紧，帮我关掉优酷续费就行，别的先不动。", CANCEL),
    ("inventory", "只帮我看看有哪些自动扣费，先不要退订。", LIST),
    ("subscription_query", "查一下我现在有哪些订阅。", LIST),
    ("ambiguous", "那个帮我弄一下。", "reply_only"),
    ("pension", "养老金到账了，帮我安排这个月的生活费和给家人的转账。", CROSS),
    ("birthday", "下周是妈妈生日，想订花和蛋糕，预算五百块，帮我安排。", CROSS),
    ("transfer", "给妈妈转三百元。", TRANSFER),
]


@pytest.mark.skipif(not os.environ.get("BANK_ROUTING_LIVE_CONFIG"), reason="explicit live routing opt-in only")
@pytest.mark.parametrize("case_id,text,expected", LIVE_CASES, ids=[row[0] for row in LIVE_CASES])
def test_live_life_goal_routing(tmp_path, case_id, text, expected):
    config = load_config(Path(os.environ["BANK_ROUTING_LIVE_CONFIG"]))
    # Secrets and risk facts stay in the existing local config; stores are fresh.
    config = config.model_copy(update={"data_directory": tmp_path / "isolated"})
    runtime = build_runtime(config)
    trusted = owner(runtime, config.demo_round_id, config.demo_user_id)
    started = monotonic()
    outcome = runtime.harness.understand(trusted, text)
    actual = "reply_only" if isinstance(outcome, ReplyOnly) else outcome.capability_name
    with closing(connect(runtime.gateway._bank.store.path)) as connection:
        operations = connection.execute("SELECT COUNT(*) FROM bank_operations").fetchone()[0]
    tasks = runtime.application.list_session_tasks(trusted.user_id, config.demo_round_id, trusted.session_id)
    record = {
        "case": case_id, "input": text, "expected": expected, "actual": actual,
        "model": config.model_name, "elapsed_seconds": round(monotonic() - started, 2),
        "model_py_sha256": hashlib.sha256(Path(__file__).with_name("model.py").read_bytes()).hexdigest(),
        "bank_operations": operations, "business_tasks": len(tasks),
        "layer": "real model planning only; no business dispatch or page E2E",
    }
    evidence = os.environ.get("BANK_ROUTING_LIVE_EVIDENCE")
    if evidence:
        path = Path(evidence)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False))
    assert operations == 0 and tasks == []
    assert actual == expected
