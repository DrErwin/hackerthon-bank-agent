"""Scenario-05 task entry: checkpointed constraints only, never raw chat text.

The platform supplies ``StartTransferInput`` for every module; this entry uses only
``request_id`` and ``intent_text`` and turns them into bank-matched decisions before
anything is persisted. Confirmation and verification stay owned by the security gate:
this entry just reports the gate's own pending step back to the frontend.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import logging
import re
from typing import Callable
from uuid import uuid4

from app.contracts.common import SecurityDecisionCode
from app.contracts.platform import StartTransferInput, TrustedContext
from app.contracts.tasks import ModuleResult
from .service import SubscriptionError, SubscriptionService


LOGGER = logging.getLogger(__name__)

_TERMINAL = {"succeeded", "failed", "cancelled"}
_CANCEL_WORDS = ("退订", "取消", "关闭", "关掉", "关了", "都关", "退了", "退掉", "别再扣", "别再",
                 "解约", "解除", "不续费", "不想续", "停了", "停掉")
_BATCH_WORDS = ("全部", "所有", "统统", "都退", "都关", "一键", "全都")
# Observed phrases from the user's own words; the security policy decides the risk level.
_HIGH_RISK_PATTERNS = {
    "screen_sharing": ("共享屏幕", "屏幕共享", "投屏", "远程控制"),
    "credential_request": ("验证码告诉", "验证码发", "把验证码", "要验证码", "索要验证码", "报验证码"),
    "third_party_instruction": ("客服让我", "客服叫我", "儿子让我", "女儿让我", "孩子让我", "别人让我",
                                "他让我", "他们让我"),
    "secrecy_or_urgency": ("别告诉", "不要告诉", "偷偷", "赶紧退", "马上退", "快点退"),
}
_MANDATE_ID = re.compile(r"sub_[A-Za-z0-9_]+")


def _actor(context: TrustedContext) -> tuple[str, str, str]:
    return context.user_id, context.demo_round_id, context.task_id


def wants_cancel(intent_text: str) -> bool:
    """The module decides what it does; the planner only routes to this module."""

    return any(word in intent_text for word in _CANCEL_WORDS)


def risk_observations(intent_text: str) -> list[str]:
    return [name for name, phrases in _HIGH_RISK_PATTERNS.items()
            if any(phrase in intent_text for phrase in phrases)]


def named_mandate_id(intent_text: str) -> str | None:
    found = _MANDATE_ID.search(intent_text)
    return found.group(0) if found else None


class SubscriptionEntry:
    """Implements the registry's task-entry protocol for scenario 05."""

    def __init__(self, service: SubscriptionService, saver, trace):
        self.service, self.saver, self.trace = service, saver, trace

    def _config(self, context, thread_id):
        return {"configurable": {"thread_id": thread_id or context.task_id, "checkpoint_ns": ""}}

    def _load(self, context, thread_id):
        saved = self.saver.get_tuple(self._config(context, thread_id))
        if saved is None:
            return None, None
        state = deepcopy(saved.checkpoint["channel_values"].get("subscription_state"))
        if not isinstance(state, dict) or tuple(state.get("actor", ())) != _actor(context):
            raise PermissionError("ACCESS_DENIED")
        return saved, state

    def _save(self, context, thread_id, state):
        saved, _ = self._load(context, thread_id)
        version = int(saved.checkpoint["channel_versions"].get("subscription_state", 0)) + 1 if saved else 1
        checkpoint = {"v": 1, "id": str(uuid4()), "ts": self.service.clock().isoformat(),
            "channel_values": {"subscription_state": deepcopy(state)},
            "channel_versions": {"subscription_state": version}, "versions_seen": {},
            "pending_sends": []}
        config = saved.config if saved else self._config(context, thread_id)
        self.saver.put(config, checkpoint, {"source": "update", "step": version, "parents": {}},
                       {"subscription_state": version})

    @staticmethod
    def _result(context, state):
        result = ModuleResult.model_validate(state["result"])
        return result.model_copy(update={"run_id": context.run_id})

    def _new_state(self, trusted: TrustedContext, request: StartTransferInput, digest: str) -> dict:
        return {"actor": list(_actor(trusted)), "session_id": trusted.session_id,
                "request_id": str(request.request_id), "intent_digest": digest,
                "mode": "cancel" if wants_cancel(request.intent_text) else "list",
                "batch": any(word in request.intent_text for word in _BATCH_WORDS),
                "mandate_id": named_mandate_id(request.intent_text),
                "risk": risk_observations(request.intent_text),
                "reminder_days": 30, "waiting": None, "selected": None, "candidates": [],
                "operation_id": None}

    def start(self, trusted: TrustedContext, request: StartTransferInput, *, thread_id=None) -> ModuleResult:
        if not isinstance(request, StartTransferInput):
            return self.service.failed(trusted, "INVALID_ARGUMENT")
        saved, state = self._load(trusted, thread_id)
        digest = sha256(request.intent_text.encode("utf-8")).hexdigest()
        if state is not None:
            if state["session_id"] != trusted.session_id:
                raise PermissionError("ACCESS_DENIED")
            if state["request_id"] != str(request.request_id) or state["intent_digest"] != digest:
                raise ValueError("REQUEST_CONFLICT")
            if "result" in state:
                return self._result(trusted, state)
        else:
            state = self._new_state(trusted, request, digest)
            self._save(trusted, thread_id, state)
        result = self._advance(trusted, state, utterance=request.intent_text)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result

    def resume(self, trusted: TrustedContext, response: dict, *, thread_id=None) -> ModuleResult:
        saved, state = self._load(trusted, thread_id)
        if state is None:
            raise ValueError("TASK_NOT_FOUND")
        if state["session_id"] != trusted.session_id:
            raise PermissionError("ACCESS_DENIED")
        if state.get("result", {}).get("status") in _TERMINAL:
            return self._result(trusted, state)
        if response.get("cancel") is True or response.get("choice") == "cancel":
            result = self.service.cancelled(trusted)
        elif state.get("waiting") == "input" and (
                response.get("selected_option_id")
                or (response.get("choice") and response.get("choice") not in {"resume", "approve"})):
            if set(response) - {"choice", "text", "selected_option_id", "interaction_id"}:
                raise ValueError("INVALID_ARGUMENT")
            choice = response.get("selected_option_id") or response.get("choice")
            if choice not in state.get("candidates", []):
                raise ValueError("INVALID_OPTION")
            result = self._advance(trusted, state, selected=choice)
        elif state.get("waiting") == "input" and str(response.get("text") or "").strip():
            result = self._advance(trusted, state, utterance=str(response["text"]).strip())
        else:
            # A confirmation or verification was answered: re-check the gate and continue.
            result = self._advance(trusted, state)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result

    def _advance(self, trusted: TrustedContext, state: dict, *,
                 utterance: str | None = None, selected: str | None = None) -> ModuleResult:
        try:
            if state["mode"] == "list":
                result = self.service.inventory(trusted, reminder_days=state["reminder_days"])
                return self.service.list_task(trusted, result, reminder_days=state["reminder_days"])
            return self._cancel_step(trusted, state, utterance=utterance, selected=selected)
        except SubscriptionError as error:
            return self.service.failed(trusted, error.code, source=error.source, upstream=error.upstream)
        except PermissionError:
            raise
        except Exception as error:  # never leak bank facts or a traceback into the reply
            LOGGER.error("subscription.internal_failure task_id=%s class=%s",
                         trusted.task_id, type(error).__name__)
            return self.service.failed(trusted, "SUBSCRIPTION_INTERNAL_ERROR")

    def _cancel_step(self, trusted: TrustedContext, state: dict, *,
                     utterance: str | None = None, selected: str | None = None) -> ModuleResult:
        if selected is not None:
            state["selected"] = selected
            state["batch"] = False
        elif state.get("mandate_id"):
            state["selected"] = state["mandate_id"]
        resolution = self.service.resolve_cancel(
            trusted, subscription_id=state.get("selected"),
            utterance=None if state.get("selected") else utterance,
            batch_requested=bool(state.get("batch")) and state.get("selected") is None,
            reminder_days=state["reminder_days"])
        state["waiting"] = None
        if resolution.kind == "candidates":
            state["candidates"] = [item.subscription_id for item in resolution.candidates]
            state["waiting"] = "input"
            return self.service.waiting_input(trusted, resolution)
        if resolution.kind == "guide":
            return self.service.completed(trusted, self.service.guide_message(resolution.item),
                                          item=resolution.item)
        if resolution.kind == "already_cancelled":
            return self.service.completed(
                trusted, self.service.already_cancelled_message(resolution.item), item=resolution.item)
        if resolution.kind == "not_found":
            return self.service.completed(trusted, self.service.not_found_message(),
                                          list_result=resolution.list_result)
        item = resolution.item
        # Persist the bank-matched target so every later step re-resolves the same row.
        state["selected"] = item.subscription_id
        plan = self.service.plan_for(item, tuple(state.get("risk") or ()))
        answer = self.service.check_cancel(trusted, plan)
        state["operation_id"] = answer.operation_id
        if answer.decision == SecurityDecisionCode.ALLOW:
            outcome = self.service.execute_cancel(trusted, plan)
            return self.service.cancel_task(trusted, item, plan, outcome)
        if answer.decision == SecurityDecisionCode.REQUIRE_CONFIRMATION:
            state["waiting"] = "confirmation"
            return self.service.waiting_approval(trusted, answer, self.service.confirmation_message(item))
        if answer.decision == SecurityDecisionCode.REQUIRE_VERIFICATION:
            state["waiting"] = "verification"
            return self.service.waiting_approval(trusted, answer, self.service.verification_message())
        if answer.decision == SecurityDecisionCode.BLOCK:
            return self.service.security_stop(trusted, answer.reason_code)
        return self.service.failed(trusted, "SECURITY_REJECTED", source="security",
                                   upstream=answer.reason_code)

    def checkpoint_context(self, trusted: TrustedContext, *, thread_id=None):
        saved, state = self._load(trusted, thread_id)
        if state is None:
            return None
        return trusted.model_copy(update={"session_id": state["session_id"]})

    def recover_session(self, trusted: TrustedContext, *, source_session_id: str, thread_id=None):
        saved, state = self._load(trusted, thread_id)
        if state is None or state["session_id"] not in {source_session_id, trusted.session_id}:
            raise PermissionError("ACCESS_DENIED")
        state["session_id"] = trusted.session_id
        # A new login session voids the old verification; the gate asks again instead.
        state["waiting"] = None
        if state.get("result", {}).get("status") in _TERMINAL:
            result = self._result(trusted, state)
        else:
            result = self._advance(trusted, state)
        state["result"] = result.model_dump(mode="json")
        self._save(trusted, thread_id, state)
        return result


def subscription_factory(ports_factory: Callable, clock: Callable):
    """The platform injects security-checked ports per task; there is no allow-all default."""

    def create(trusted, saver, trace):
        return SubscriptionEntry(SubscriptionService(ports_factory(trusted, trace), clock), saver, trace)
    return create


def register_subscription(registry, ports_factory: Callable, clock: Callable):
    from .manifest import MANIFEST
    registry.register_module(MANIFEST, subscription_factory(ports_factory, clock))
