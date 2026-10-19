"""Server-owned risk inputs for the security risk detector (Issue #160).

The detector never reads storage itself. This module is the only place that
associates the original request with the immutable facts of one action, after
checking the trusted subject, session, demo round, task and parameters ref.
Facts that the platform cannot obtain stay ``unknown``; this module never
substitutes a lower risk level for a missing fact.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import TYPE_CHECKING, Literal

from pydantic import TypeAdapter

from app.contracts.bank import (
    PayeeDisplay, PayeeInput, PayeeVerification, QueryFailure, QueryOk, Transaction,
)
from app.contracts.common import TaskStatus
from app.contracts.platform import CapabilityDefinition, TrustedContext
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext
from app.modules.transfer.tools import TransferSnapshots
from app.services.bank_gateway.gateway import BankGateway
from app.storage.application import ApplicationStore, TaskRecord

if TYPE_CHECKING:  # The detector lives in app.security; importing it here would cycle.
    from app.security.demo_policy import DemoRiskEvidence


TRANSFER_WRITE = "bank.submit_transfer"
HISTORY_WINDOW = timedelta(days=180)
AMOUNT_MULTIPLE = 2
RISK_INPUTS_VERSION = "v04-risk-inputs-1"

TASK_BINDING_REQUIRED = "risk-input-task-binding-required"
REQUEST_BINDING_REQUIRED = "risk-input-request-binding-required"
ACTION_BINDING_REQUIRED = "risk-input-action-binding-required"
ACTION_UNSUPPORTED = "risk-input-action-unsupported"

_TERMINAL = frozenset({TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED})
_FACT_NAMES = ("payee_history", "amount_history", "environment")
_PAYEE = TypeAdapter(PayeeInput)
_EVIDENCE_PREFIX = "risk-inputs-"
_EVIDENCE_LENGTH = 24

# FactName mirrors _FACT_NAMES for typing; _FACT_NAMES is the runtime source.
FactName = Literal["payee_history", "amount_history", "environment"]
RiskDetector = Callable[["RiskInputs"], "DemoRiskEvidence"]


@dataclass(frozen=True)
class RiskFact:
    """One risk dimension with its actual source and checked scope.

    ``known`` always carries a value and the source that produced it; ``unknown``
    never carries a value. An unknown fact means the dimension was not checked:
    the detector must not read it as a safe result, and must not report it as a
    checked signal dimension.
    """

    name: FactName
    status: Literal["known", "unknown"]
    source: str
    scope: str
    value: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if self.name not in _FACT_NAMES:
            raise ValueError("risk input fact name is not registered")
        if self.status not in {"known", "unknown"}:
            raise ValueError("risk input fact status must be known or unknown")
        for label in (self.source, self.scope):
            if not isinstance(label, str) or not label.strip():
                raise ValueError("risk input facts require a source and a checked scope")
        if self.status == "known":
            if not isinstance(self.value, Mapping) or not self.value:
                raise ValueError("known risk input facts require their values")
        elif self.value is not None:
            raise ValueError("unknown risk input facts must not carry values")

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name, "status": self.status, "source": self.source,
            "scope": self.scope, "value": dict(self.value) if self.value is not None else None,
        }


@dataclass(frozen=True)
class RiskInputs:
    """Raw request plus immutable action facts, bound to one trusted scope.

    ``request_text`` and ``action_facts`` are only for the in-process detector;
    the opaque ``evidence_ref`` is the only value that may reach audit evidence.
    """

    user_id: str
    session_id: str
    demo_round_id: str
    task_id: str
    run_id: str
    request_id: str
    request_text: str = field(repr=False)
    action_name: str
    parameters_ref: str
    operation_id: str | None
    action_revision: int | None
    action_facts: Mapping[str, object] = field(repr=False)
    facts: tuple[RiskFact, ...]
    evidence_ref: str

    def __post_init__(self) -> None:
        for label in (self.user_id, self.session_id, self.demo_round_id, self.task_id,
                      self.run_id, self.request_id, self.action_name, self.parameters_ref):
            if not isinstance(label, str) or not label.strip():
                raise ValueError("risk inputs require every binding identifier")
        if not isinstance(self.request_text, str) or not self.request_text.strip():
            raise ValueError("risk inputs require the original request text")
        if not isinstance(self.action_facts, Mapping) or not self.action_facts:
            raise ValueError("risk inputs require the immutable action facts")
        if tuple(fact.name for fact in self.facts) != _FACT_NAMES:
            raise ValueError("risk inputs must carry every registered fact once")
        if not isinstance(self.evidence_ref, str) or not self.evidence_ref.startswith(
            _EVIDENCE_PREFIX
        ) or len(self.evidence_ref) != len(_EVIDENCE_PREFIX) + _EVIDENCE_LENGTH:
            raise ValueError("risk input evidence reference must be an opaque digest")

    def fact(self, name: FactName) -> RiskFact:
        for fact in self.facts:
            if fact.name == name:
                return fact
        raise KeyError(name)  # pragma: no cover - constructor enforces every fact


class TrustedRiskInputs:
    """Resolve the original request and action facts for a detector.

    Callers may only receive ``RiskInputs``; the raw request, account numbers and
    action facts never leave this process except through the opaque evidence ref.
    """

    def __init__(
        self,
        application: ApplicationStore,
        snapshots: TransferSnapshots,
        gateway: BankGateway,
        *,
        history_window: timedelta = HISTORY_WINDOW,
        amount_multiple: int = AMOUNT_MULTIPLE,
        clock: Callable[[], datetime] | None = None,
        policy_version: str = RISK_INPUTS_VERSION,
    ) -> None:
        if history_window <= timedelta(0):
            raise ValueError("risk input history window must be positive")
        if not isinstance(amount_multiple, int) or amount_multiple < 1:
            raise ValueError("risk input amount multiple must be a positive integer")
        self.application = application
        self.snapshots = snapshots
        self.gateway = gateway
        self.history_window = history_window
        self.amount_multiple = amount_multiple
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.policy_version = policy_version

    def resolve(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        declaration: CapabilityDefinition,
    ) -> RiskInputs:
        if (
            declaration.name != TRANSFER_WRITE
            or action.action_name != TRANSFER_WRITE
            or declaration.side_effect is not True
        ):
            self._unavailable(ACTION_UNSUPPORTED)
        task = self._task(context)
        request_id, request_text = self._request(task)
        action_facts, payee = self._action_facts(context, action)
        facts = self._facts(context, action_facts, payee)
        reference = self._evidence_ref(context, action, request_id, request_text, facts)
        return RiskInputs(
            user_id=context.user_id, session_id=context.session_id,
            demo_round_id=context.demo_round_id, task_id=context.task_id,
            run_id=context.run_id, request_id=request_id, request_text=request_text,
            action_name=action.action_name, parameters_ref=action.parameters_ref,
            operation_id=str(context.operation_id) if context.operation_id else None,
            action_revision=context.action_revision, action_facts=action_facts,
            facts=facts, evidence_ref=reference,
        )

    def _task(self, context: ExecutionSecurityContext) -> TaskRecord:
        task = self.application.get_task(
            context.user_id, context.demo_round_id, context.task_id,
        )
        if (
            task is None
            or task.session_id != context.session_id
            or task.status in _TERMINAL
        ):
            self._unavailable(TASK_BINDING_REQUIRED)
        return task

    def _request(self, task: TaskRecord) -> tuple[str, str]:
        request_id = task.snapshot.get("request_id")
        request_text = task.snapshot.get("intent_text")
        if (
            not isinstance(request_id, str) or not request_id.strip()
            or not isinstance(request_text, str) or not request_text.strip()
        ):
            self._unavailable(REQUEST_BINDING_REQUIRED)
        return request_id, request_text

    def _action_facts(
        self, context: ExecutionSecurityContext, action: ActionDescriptor,
    ) -> tuple[dict[str, object], PayeeInput]:
        try:
            payload = self.snapshots.resolve(context, action)
        except ValueError:
            self._unavailable(ACTION_BINDING_REQUIRED)
        if not isinstance(payload, dict):
            self._unavailable(ACTION_BINDING_REQUIRED)
        payer = payload.get("payer_account_id")
        amount = payload.get("amount_fen")
        raw_payee = payload.get("payee")
        if (
            not isinstance(payer, str) or not payer.strip()
            or not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0
            or not isinstance(raw_payee, dict)
        ):
            self._unavailable(ACTION_BINDING_REQUIRED)
        try:
            payee = _PAYEE.validate_python(raw_payee)
        except Exception:
            self._unavailable(ACTION_BINDING_REQUIRED)
        # Detached copy: the snapshot store must never be mutable through a fact.
        facts = json.loads(json.dumps(payload, ensure_ascii=False))
        return facts, payee

    def _facts(
        self, context: ExecutionSecurityContext, action_facts: Mapping[str, object],
        payee: PayeeInput,
    ) -> tuple[RiskFact, ...]:
        trusted = TrustedContext(
            user_id=context.user_id, session_id=context.session_id,
            demo_round_id=context.demo_round_id, task_id=context.task_id,
            run_id=context.run_id, parent_task_id=context.source_task_id,
        )
        amount_fen = int(action_facts["amount_fen"])
        payer_account_id = str(action_facts["payer_account_id"])
        end = self.clock()
        start = end - self.history_window
        verification = self.gateway.verify_payee(trusted, payee)
        history = self.gateway.list_transactions(trusted, payer_account_id, start, end)
        failure_code = history.error.code if isinstance(history, QueryFailure) else None
        transactions = history.data.transactions if failure_code is None else None
        display = None
        if not isinstance(verification, QueryFailure):
            display = verification.data.payee if verification.data.matched else None
        payee_fact = self._payee_fact(verification, failure_code, transactions, display)
        amount_fact = self._amount_fact(failure_code, transactions, amount_fen)
        environment = RiskFact(
            name="environment", status="unknown",
            source="platform:no-trusted-device-source",
            scope="当前 API 与任务快照没有设备指纹来源；环境维度未检查",
        )
        return (payee_fact, amount_fact, environment)

    def _payee_fact(
        self, verification: QueryOk[PayeeVerification] | QueryFailure,
        failure_code: str | None, transactions: list[Transaction] | None,
        display: PayeeDisplay | None,
    ) -> RiskFact:
        """The facts of this payee, not a risk verdict: saved status and prior outflows.

        In the current bank path a payee only reaches a write action after B04
        resolved it, so a known fact always carries ``saved=True``; the detector
        tells "常用收款人" from "新收款人" by ``prior_outflows``.
        """
        window = int(self.history_window.total_seconds() // 86400)
        if isinstance(verification, QueryFailure):
            return RiskFact(
                name="payee_history", status="unknown",
                source=f"mock-bank:{verification.error.code}",
                scope=f"收款人核验读取失败，无法确认对手方；近 {window} 天流水未检查",
            )
        if display is None:
            return RiskFact(
                name="payee_history", status="unknown",
                source="mock-bank:b04",
                scope="收款人无法解析为银行已存收款人；熟悉度未检查",
            )
        if transactions is None:
            return RiskFact(
                name="payee_history", status="unknown",
                source=f"mock-bank:{failure_code}",
                scope=f"收款人已解析，但近 {window} 天流水读取失败；熟悉度未检查",
            )
        prior = [
            item for item in transactions
            if item.direction == "outflow" and (
                item.counterparty_id == display.payee_id
                or item.counterparty_account_masked == display.account_masked
            )
        ]
        return RiskFact(
            name="payee_history", status="known", source="mock-bank:b04+b08",
            scope=f"本人账户近 {window} 天转出流水 + 银行已存收款人核验",
            value={"saved": verification.data.matched, "prior_outflows": len(prior)},
        )

    def _amount_fact(
        self, failure_code: str | None, transactions: list[Transaction] | None,
        amount_fen: int,
    ) -> RiskFact:
        window = int(self.history_window.total_seconds() // 86400)
        if transactions is None:
            return RiskFact(
                name="amount_history", status="unknown",
                source=f"mock-bank:{failure_code}",
                scope=f"近 {window} 天转出流水读取失败；金额习惯未检查",
            )
        prior = [
            item.amount_fen for item in transactions
            if item.direction == "outflow" and item.nature == "transfer"
        ]
        if not prior:
            return RiskFact(
                name="amount_history", status="unknown", source="mock-bank:b08",
                scope=f"本人账户近 {window} 天没有可比较的转出转账样本",
            )
        baseline = max(prior)
        return RiskFact(
            name="amount_history", status="known", source="mock-bank:b08",
            scope=f"本人转出账户近 {window} 天转出转账金额",
            value={"amount_fen": amount_fen, "sample_size": len(prior),
                   "baseline_max_fen": baseline, "multiple": self.amount_multiple,
                   "usual": amount_fen <= self.amount_multiple * baseline},
        )

    def _evidence_ref(
        self, context: ExecutionSecurityContext, action: ActionDescriptor,
        request_id: str, request_text: str, facts: tuple[RiskFact, ...],
    ) -> str:
        canonical = {
            # run_id is deliberately absent: recovery moves the task to a new run
            # while the trusted scope and immutable inputs stay the same.
            "binding": {
                "user_id": context.user_id, "session_id": context.session_id,
                "demo_round_id": context.demo_round_id, "task_id": context.task_id,
                "action_name": action.action_name,
                "parameters_ref": action.parameters_ref,
                "operation_id": str(context.operation_id) if context.operation_id else None,
                "action_revision": context.action_revision,
            },
            "request": {
                "request_id": request_id,
                "text_sha256": sha256(request_text.encode("utf-8")).hexdigest(),
            },
            "facts": [fact.as_dict() for fact in facts],
        }
        digest = sha256(json.dumps(
            canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return f"{_EVIDENCE_PREFIX}{digest[:_EVIDENCE_LENGTH]}"

    def _unavailable(self, rule_id: str) -> None:
        raise self._binding_error(rule_id) from None

    def _binding_error(self, rule_id: str) -> RuntimeError:
        # Imported locally so this module stays importable while app.security loads.
        from app.security.gate import RiskFactsUnavailable

        return RiskFactsUnavailable(
            "trusted risk inputs are unavailable",
            rule_id=rule_id, policy_version=self.policy_version,
        )
