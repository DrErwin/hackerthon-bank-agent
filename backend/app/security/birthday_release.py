"""§3.5 limited release: authorization records and the controlled ending.

Server-side usage:

- When the user answers the freeze confirmation, call
  ``grant_release_authorization`` (only an approved ``bank.freeze_funds``
  confirmation that displayed the §3.5 clause grants anything; the record
  starts ``pending_freeze``).
- When the freeze result is known — or is re-queried by its original
  operation id after an unknown outcome — call ``bind_freeze_result``
  (success binds the bank freeze_id and turns the record ``active``; a
  definite failure makes it ``invalid``; unknown stays pending).
- At task end (completed, cancelled, or security-terminated) the controlled
  path calls ``LimitedReleaseFinalizer.finalize``. It verifies the trusted
  identity, the ended task, resolved in-flight actions, and the bank's own
  freeze facts, then releases exactly the bank-verified remainder under a
  fresh persisted operation id. It never asks the user again, never resumes
  the terminated task, and submits nothing when the remainder is zero.

``bank.release_frozen`` stays off the model tool registry: the ordinary
executor refuses it as unregistered, so the model cannot initiate or widen a
release. The bank gateway's ``authorize_birthday`` callback is satisfied by
``authorize_birthday_write``, which binds the caller identity, operation id,
action name, and a live allow claim; the submitted parameters are bound by
the bank's per-operation parameter digest (same id plus different parameters
is a conflict) together with the claim's parameters_ref. If a stronger
callback contract (parameters visible at the callback) is ever needed, that
is a gateway/provider change, not a security-side relaxation.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from app.contracts.bank import (
    OperationFound, OperationNotFound, OperationResult, QueryFailure, ReleaseFrozenInput,
)
from app.contracts.common import (
    OperationLevel, Phase, RiskLevel, SecurityDecisionCode,
)
from app.contracts.platform import TrustedContext
from app.contracts.security import (
    ActionDescriptor, ConfirmationRecord, ExecutionSecurityContext, SecurityDecision,
)
from app.security.birthday_policy import has_release_clause
from app.security.gate import SecurityError
from app.security.state import FreezeReleaseAuthorization, SQLiteSecurityState


POLICY_VERSION = "v05-birthday-limited-release-1"


@dataclass(frozen=True)
class ReleaseOutcome:
    """The observable ending: what the caller may report to the user."""

    status: Literal["released", "nothing_to_release", "needs_attention", "blocked"]
    decision: SecurityDecision
    authorization: FreezeReleaseAuthorization | None
    release_operation_id: UUID | None
    released_amount_fen: int | None
    remaining_fen: int | None
    consumed_total_fen: int | None
    evidence_refs: list[str] = field(default_factory=list)


def _yuan(fen: int) -> str:
    return f"{fen / 100:.2f} 元"


def grant_release_authorization(
    state: SQLiteSecurityState,
    context: ExecutionSecurityContext,
    confirmation: ConfirmationRecord,
    *,
    account_id: str,
    amount_fen: int,
    now: datetime,
) -> FreezeReleaseAuthorization:
    """Turn an approved clause-bearing freeze confirmation into the record."""
    if confirmation.decision != "approved":
        raise SecurityError("CONFIRMATION_REQUIRED")
    if confirmation.action_name != "bank.freeze_funds":
        raise SecurityError("POLICY_VIOLATION")
    if (
        confirmation.user_id, confirmation.session_id,
        confirmation.demo_round_id, confirmation.task_id,
    ) != (
        context.user_id, context.session_id,
        context.demo_round_id, context.task_id,
    ):
        raise SecurityError("ACCESS_DENIED")
    if str(confirmation.operation_id) != str(context.operation_id):
        raise SecurityError("POLICY_VIOLATION")
    if not has_release_clause(confirmation.display_fields):
        raise SecurityError("POLICY_VIOLATION")
    if amount_fen <= 0:
        raise SecurityError("INPUT_REQUIRED")
    record = FreezeReleaseAuthorization(
        release_authorization_id="rel_" + uuid4().hex[:16],
        user_id=context.user_id,
        session_id=context.session_id,
        demo_round_id=context.demo_round_id,
        task_id=context.task_id,
        account_id=account_id,
        freeze_operation_id=context.operation_id,
        freeze_id=None,
        confirmation_id=confirmation.confirmation_id,
        confirmation_version=confirmation.confirmation_version,
        max_amount_fen=amount_fen,
        granted_at=now,
        status="pending_freeze",
        action_revision=confirmation.action_revision,
    )
    try:
        return state.store_release_authorization(record)
    except ValueError as exc:
        raise SecurityError(getattr(exc, "code", "DEPENDENCY_UNAVAILABLE")) from exc


def bind_freeze_result(
    state: SQLiteSecurityState,
    context: ExecutionSecurityContext,
    release_authorization_id: str,
    lookup,
    now: datetime,
) -> FreezeReleaseAuthorization:
    """Bind the bank's freeze outcome (or its unresolved lookup) to the record.

    ``lookup`` is the bank operation observation for the original freeze
    operation id: an ``OperationResult``, the gateway's ``OperationFound``
    wrapper, an ``OperationNotFound``, or a ``QueryFailure``. Unknown outcomes
    leave the record pending; only a definite success with the confirmed
    amount activates it.
    """
    del now  # the bank observation carries its own timestamps
    authorization = _load(state, context, release_authorization_id)
    if isinstance(lookup, QueryFailure):
        if lookup.error.code == "ACCESS_DENIED":
            raise SecurityError("ACCESS_DENIED")
        return authorization
    if isinstance(lookup, OperationNotFound):
        return authorization
    operation = lookup.operation if isinstance(lookup, OperationFound) else lookup
    if not isinstance(operation, OperationResult):
        raise SecurityError("POLICY_VIOLATION")
    if str(operation.operation_id) != str(authorization.freeze_operation_id):
        raise SecurityError("OPERATION_CONFLICT")
    if operation.operation_status == "succeeded":
        receipt = operation.receipt
        if receipt is None or receipt.frozen_amount_fen != authorization.max_amount_fen:
            raise SecurityError("POLICY_VIOLATION")
        updated = authorization.model_copy(update={
            "status": "active", "freeze_id": receipt.freeze_id,
        })
    elif operation.operation_status == "failed":
        updated = authorization.model_copy(update={"status": "invalid"})
    else:
        return authorization
    return _update(state, context, updated)


def authorize_birthday_write(state: SQLiteSecurityState) -> Callable[..., bool]:
    """Wire this into BankGateway(authorize_birthday=...).

    The gateway passes (trusted context, operation id, action name) and, once
    v05-cross-platform/10 lands, the typed request as a fourth argument. The
    decision binds identity, operation id, action name, and a live allow
    claim; a release claim additionally carries its exact payload
    (freeze id plus amount) in parameters_ref, so a passed request must match
    it field by field. No claim, foreign identity, wrong action, replayed
    completed claim, non-allow decision, or mismatched request ever passes —
    there is no constant-true callback here.
    """

    def authorize(trusted_context: TrustedContext, operation_id: UUID,
                  action: str, request=None) -> bool:
        try:
            claim = state.find_execution(operation_id)
        except Exception:
            return False
        if claim is None or claim.decision is None:
            return False
        if (
            claim.user_id, claim.demo_round_id, claim.task_id,
        ) != (
            trusted_context.user_id, trusted_context.demo_round_id,
            trusted_context.task_id,
        ):
            return False
        if claim.action_name != action or claim.state != "processing":
            return False
        if claim.decision.decision is not SecurityDecisionCode.ALLOW:
            return False
        binding = _release_payload_binding(claim.parameters_ref)
        if binding is None or request is None:
            # Purchase claims bind parameters through the platform's snapshot
            # comparison (as transfer does); until the gateway forwards the
            # request, release claims keep the identity-plus-claim binding.
            return True
        return (getattr(request, "freeze_id", None),
                getattr(request, "amount_fen", None)) == binding

    return authorize


def _release_payload_binding(parameters_ref: str) -> tuple[str, int] | None:
    """Parse the exact payload a release claim binds: (freeze_id, amount)."""
    parts = parameters_ref.split(":")
    if len(parts) != 4 or parts[0] != "release":
        return None
    try:
        return parts[2], int(parts[3])
    except ValueError:
        return None


def _load(
    state: SQLiteSecurityState,
    context: ExecutionSecurityContext,
    release_authorization_id: str,
) -> FreezeReleaseAuthorization:
    try:
        record = state.get_release_authorization(context, release_authorization_id)
    except ValueError as exc:
        raise SecurityError(getattr(exc, "code", "DEPENDENCY_UNAVAILABLE")) from exc
    if record is None:
        raise SecurityError("POLICY_VIOLATION")
    return record


def _update(
    state: SQLiteSecurityState,
    context: ExecutionSecurityContext,
    record: FreezeReleaseAuthorization,
) -> FreezeReleaseAuthorization:
    try:
        return state.update_release_authorization(context, record)
    except ValueError as exc:
        raise SecurityError(getattr(exc, "code", "DEPENDENCY_UNAVAILABLE")) from exc


FreezeReader = Callable[[TrustedContext, str], object]
OperationReader = Callable[[TrustedContext, UUID], object]
BankRelease = Callable[[TrustedContext, UUID, object], object]
DecisionSink = Callable[[SecurityDecision], None]
SnapshotWriter = Callable[
    [ExecutionSecurityContext, ConfirmationRecord | None, tuple, datetime], str,
]
TaskStateResolver = Callable[[ExecutionSecurityContext], bool]
Clock = Callable[[], datetime]


class LimitedReleaseFinalizer:
    """The controlled §3.5 ending for one security state store."""

    def __init__(
        self,
        state: SQLiteSecurityState,
        *,
        decision_sink: DecisionSink,
        snapshot_writer: SnapshotWriter,
        task_state_resolver: TaskStateResolver,
        freeze_reader: FreezeReader,
        operation_reader: OperationReader,
        bank_release: BankRelease,
        clock: Clock,
        operation_factory: Callable[[], UUID] = uuid4,
        current_demo_round: Callable[[], str] | None = None,
    ) -> None:
        self.state = state
        self.decision_sink = decision_sink
        self.snapshot_writer = snapshot_writer
        self.task_state_resolver = task_state_resolver
        self.freeze_reader = freeze_reader
        self.operation_reader = operation_reader
        self.bank_release = bank_release
        self.clock = clock
        self.operation_factory = operation_factory
        self.current_demo_round = current_demo_round

    # --- decision plumbing ---

    def _decision(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        *,
        operation_id: UUID | None,
        decision: SecurityDecisionCode,
        reasons: list[str],
        rules: list[str],
        message: str,
        snapshot_ref: str | None = None,
        risk: RiskLevel | None = None,
    ) -> SecurityDecision:
        return SecurityDecision(
            decision_id=str(uuid4()),
            task_id=context.task_id,
            run_id=context.run_id,
            action_name=action.action_name,
            parameters_ref=action.parameters_ref,
            operation_id=operation_id,
            action_revision=1 if operation_id is not None else None,
            phase=action.phase,
            operation_level=OperationLevel.SENSITIVE,
            risk_level=risk,
            decision=decision,
            reason_codes=reasons,
            rule_ids=rules,
            policy_version=POLICY_VERSION,
            authorization_snapshot_ref=snapshot_ref,
            evidence_refs=[],
            interaction=None,
            checked_at=self.clock(),
            message=message,
        )

    def _stop(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        authorization: FreezeReleaseAuthorization | None,
        *,
        status: Literal["released", "nothing_to_release", "needs_attention", "blocked"],
        code: SecurityDecisionCode,
        reasons: list[str],
        rules: list[str],
        message: str,
        operation_id: UUID | None = None,
        released_amount_fen: int | None = None,
        remaining_fen: int | None = None,
        consumed_total_fen: int | None = None,
        snapshot_ref: str | None = None,
        risk: RiskLevel | None = None,
        evidence_refs: list[str] | None = None,
    ) -> ReleaseOutcome:
        decision = self._decision(
            context, action, operation_id=operation_id, decision=code,
            reasons=reasons, rules=rules, message=message,
            snapshot_ref=snapshot_ref, risk=risk,
        )
        final_status = status
        try:
            self.decision_sink(decision)
        except Exception:
            decision = self._decision(
                context, action, operation_id=operation_id,
                decision=SecurityDecisionCode.PAUSE,
                reasons=["AUDIT_UNAVAILABLE"], rules=[*rules, "audit-before-release"],
                message="安全记录暂不可用，释放已暂停。",
            )
            final_status = "needs_attention"
        return ReleaseOutcome(
            status=final_status,
            decision=decision,
            authorization=authorization,
            release_operation_id=operation_id,
            released_amount_fen=released_amount_fen,
            remaining_fen=remaining_fen,
            consumed_total_fen=consumed_total_fen,
            evidence_refs=evidence_refs or [],
        )

    @staticmethod
    def _trusted(context: ExecutionSecurityContext) -> TrustedContext:
        return TrustedContext(
            user_id=context.user_id, session_id=context.session_id,
            demo_round_id=context.demo_round_id, task_id=context.task_id,
            run_id=context.run_id, parent_task_id=context.source_task_id,
        )

    def _record(
        self, authorization: FreezeReleaseAuthorization,
    ) -> ActionDescriptor:
        return ActionDescriptor(
            action_name="bank.release_frozen",
            parameters_ref=f"release:{authorization.release_authorization_id}",
            resource_refs=[
                authorization.freeze_id or str(authorization.freeze_operation_id),
                authorization.account_id,
            ],
            phase=Phase.EXECUTION,
        )

    @staticmethod
    def _release_action(
        authorization: FreezeReleaseAuthorization, freeze_id: str, amount_fen: int,
    ) -> ActionDescriptor:
        """The release action binds its exact payload in parameters_ref."""
        return ActionDescriptor(
            action_name="bank.release_frozen",
            parameters_ref=(
                f"release:{authorization.release_authorization_id}"
                f":{freeze_id}:{amount_fen}"
            ),
            resource_refs=[freeze_id, authorization.account_id],
            phase=Phase.EXECUTION,
        )

    def _observe(
        self, context: ExecutionSecurityContext, operation_id: UUID,
    ):
        try:
            return self.operation_reader(self._trusted(context), operation_id)
        except Exception as exc:
            raise SecurityError("DEPENDENCY_UNAVAILABLE") from exc

    # --- recovery for a release this authorization already claimed ---

    def _recover(
        self,
        context: ExecutionSecurityContext,
        authorization: FreezeReleaseAuthorization,
        operation_id: UUID,
    ) -> ReleaseOutcome:
        evidence = [authorization.release_authorization_id, str(operation_id)]
        claim = None
        try:
            claim = self.state.find_execution(operation_id)
        except ValueError:
            claim = None
        parameters_ref = (
            claim.parameters_ref if claim is not None
            else f"release:{authorization.release_authorization_id}"
        )
        action = ActionDescriptor(
            action_name="bank.release_frozen",
            parameters_ref=parameters_ref,
            resource_refs=[
                authorization.freeze_id or str(authorization.freeze_operation_id),
                authorization.account_id,
            ],
            phase=Phase.EXECUTION,
        )
        snapshot_ref = (
            claim.decision.authorization_snapshot_ref
            if claim is not None and claim.decision is not None else None
        )
        try:
            lookup = self._observe(context, operation_id)
        except SecurityError:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["OPERATION_UNKNOWN"],
                rules=["release-unknown-keep-original-id"],
                message="释放结果仍未核实，保留原编号待处理。",
                operation_id=operation_id, evidence_refs=evidence,
            )
        submit_context = context.model_copy(update={
            "operation_id": operation_id, "action_revision": 1,
        })
        if isinstance(lookup, QueryFailure) or isinstance(lookup, OperationNotFound):
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["OPERATION_UNKNOWN"],
                rules=["release-unknown-keep-original-id"],
                message="释放结果仍未核实，保留原编号待处理。",
                operation_id=operation_id, evidence_refs=evidence,
            )
        operation = lookup.operation
        if operation.operation_status == "succeeded":
            receipt = operation.receipt
            try:
                self.state.record_execution(
                    submit_context, action, "completed", str(operation_id),
                )
                completed = _update(self.state, context, authorization.model_copy(
                    update={"status": "completed"},
                ))
            except ValueError as exc:
                return self._stop(
                    context, action, authorization, status="needs_attention",
                    code=SecurityDecisionCode.PAUSE,
                    reasons=["DEPENDENCY_UNAVAILABLE"],
                    rules=["release-state-write-required"],
                    message="释放结果暂不可记录，保留待处理。",
                    operation_id=operation_id, evidence_refs=evidence,
                )
            return self._stop(
                context, action, completed, status="released",
                code=SecurityDecisionCode.ALLOW, reasons=["SECURITY_CHECK_PASSED"],
                rules=["limited-release-verified-by-original-operation"],
                message="已按原编号核实释放完成。",
                operation_id=operation_id,
                released_amount_fen=(receipt.released_amount_fen if receipt else None),
                remaining_fen=(receipt.remaining_fen if receipt else None),
                snapshot_ref=snapshot_ref,
                risk=RiskLevel.LOW, evidence_refs=evidence,
            )
        try:
            self.state.record_execution(
                submit_context, action, "completed", str(operation_id),
            )
        except ValueError:
            pass
        return self._stop(
            context, action, authorization, status="needs_attention",
            code=SecurityDecisionCode.PAUSE, reasons=["RELEASE_FAILED"],
            rules=["release-failed-keeps-original-id"],
            message="释放未成功，保留原编号待处理。",
            operation_id=operation_id, evidence_refs=evidence,
        )

    # --- the ending itself ---

    def finalize(
        self,
        context: ExecutionSecurityContext,
        end_reason: str,
    ) -> ReleaseOutcome:
        try:
            authorization = (
                self.state.get_release_authorization(
                    context, context.release_authorization_id,
                )
                if context.release_authorization_id is not None else None
            )
        except ValueError as exc:
            authorization = None
            foreign = getattr(exc, "code", None) == "ACCESS_DENIED"
            placeholder = ActionDescriptor(
                action_name="bank.release_frozen",
                parameters_ref="release:unknown", resource_refs=[],
                phase=Phase.EXECUTION,
            )
            return self._stop(
                context, placeholder, None,
                status="blocked",
                code=SecurityDecisionCode.BLOCK,
                reasons=(["ACCESS_DENIED"] if foreign else ["DEPENDENCY_UNAVAILABLE"]),
                rules=["release-owner-must-match"],
                message="无权使用该结束释放授权。",
            )
        if authorization is None:
            placeholder = ActionDescriptor(
                action_name="bank.release_frozen",
                parameters_ref="release:unknown", resource_refs=[],
                phase=Phase.EXECUTION,
            )
            return self._stop(
                context, placeholder, None, status="blocked",
                code=SecurityDecisionCode.BLOCK, reasons=["POLICY_VIOLATION"],
                rules=["release-authorization-required"],
                message="未找到有效的结束释放授权。",
            )
        action = self._record(authorization)
        evidence = [authorization.release_authorization_id,
                    str(authorization.freeze_operation_id)]
        if authorization.freeze_id is not None:
            evidence.append(authorization.freeze_id)
        if isinstance(end_reason, str) and end_reason:
            evidence.append(f"end_reason:{end_reason}")

        # A cleared demo round retires its authorizations; an old round's
        # controlled identity cannot finalize into the current round.
        if self.current_demo_round is not None:
            try:
                current_round = self.current_demo_round()
            except Exception:
                current_round = None
            if (
                not isinstance(current_round, str)
                or not current_round
                or current_round != authorization.demo_round_id
            ):
                return self._stop(
                    context, action, authorization, status="blocked",
                    code=SecurityDecisionCode.BLOCK, reasons=["STALE_ROUND"],
                    rules=["current-round-required-for-release"],
                    message="演示轮次已变化，该结束释放授权已失效。",
                    evidence_refs=evidence,
                )

        # A pending freeze is resolved by its original operation id first.
        if authorization.status == "pending_freeze":
            try:
                lookup = self._observe(context, authorization.freeze_operation_id)
                authorization = bind_freeze_result(
                    self.state, context, authorization.release_authorization_id,
                    lookup, self.clock(),
                )
            except SecurityError as exc:
                return self._stop(
                    context, action, authorization, status="blocked",
                    code=SecurityDecisionCode.BLOCK, reasons=[exc.code],
                    rules=["freeze-binding-required"],
                    message="冻结结果与确认不一致，不能释放。",
                    evidence_refs=evidence,
                )
            if authorization.status == "pending_freeze":
                return self._stop(
                    context, action, authorization, status="needs_attention",
                    code=SecurityDecisionCode.PAUSE, reasons=["OPERATION_UNKNOWN"],
                    rules=["freeze-unknown-verify-first"],
                    message="冻结结果未核实，暂不释放。",
                    evidence_refs=evidence,
                )
        if authorization.status == "invalid":
            if authorization.invalid_reason == "RETIRED_UNSUBMITTED":
                # The attempt was withdrawn before any bank submission: there is
                # no freeze and this is not a real bank failure.
                return self._stop(
                    context, action, authorization, status="nothing_to_release",
                    code=SecurityDecisionCode.BLOCK, reasons=["RETIRED_UNSUBMITTED"],
                    rules=["retired-unsubmitted-has-no-release"],
                    message="旧动作未提交，没有该笔冻结，无需释放。",
                    evidence_refs=evidence,
                )
            return self._stop(
                context, action, authorization, status="blocked",
                code=SecurityDecisionCode.BLOCK, reasons=["FREEZE_FAILED"],
                rules=["failed-freeze-has-no-release"],
                message="冻结未成功，没有可释放的余额。",
                evidence_refs=evidence,
            )
        if authorization.status == "completed":
            existing = None
            try:
                existing = self.state.release_claim(
                    context, authorization.release_authorization_id,
                )
            except ValueError:
                existing = None
            if existing is not None:
                return self._recover(context, authorization, UUID(existing.operation_id))
            return self._stop(
                context, action, authorization, status="nothing_to_release",
                code=SecurityDecisionCode.BLOCK, reasons=["ALREADY_COMPLETED"],
                rules=["release-already-completed"],
                message="结束释放已完成，无剩余冻结。",
                evidence_refs=evidence,
            )

        # The task must have ended; a running task must never release early.
        try:
            ended = self.task_state_resolver(context)
            ended = ended if isinstance(ended, bool) else None
        except Exception:
            ended = None
        if ended is None:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["DEPENDENCY_UNAVAILABLE"],
                rules=["trusted-task-state-required"],
                message="暂时无法核对任务状态，释放已暂停。",
                evidence_refs=evidence,
            )
        if not ended:
            return self._stop(
                context, action, authorization, status="blocked",
                code=SecurityDecisionCode.BLOCK, reasons=["POLICY_VIOLATION"],
                rules=["release-requires-ended-task"],
                message="任务尚未结束，不能提前释放冻结余额。",
                evidence_refs=evidence,
            )

        # A release this authorization already claimed resolves by its id.
        try:
            existing = self.state.release_claim(
                context, authorization.release_authorization_id,
            )
        except ValueError as exc:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=[getattr(exc, "code", "DEPENDENCY_UNAVAILABLE")],
                rules=["release-state-read-required"],
                message="释放状态暂不可读取，保留待处理。",
                evidence_refs=evidence,
            )
        if existing is not None:
            return self._recover(context, authorization, UUID(existing.operation_id))

        # Every other money action of this task must be resolved.
        try:
            unresolved = self.state.unresolved_executions(context)
        except ValueError:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["DEPENDENCY_UNAVAILABLE"],
                rules=["in-flight-verified-before-release"],
                message="在途动作暂不可核对，释放已暂停。",
                evidence_refs=evidence,
            )
        if unresolved:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["OPERATION_UNKNOWN"],
                rules=["in-flight-verified-before-release"],
                message="仍有在途资金动作未核实，暂不释放。",
                evidence_refs=evidence + unresolved,
            )

        # Bank facts decide the exact remainder; nothing else.
        if authorization.freeze_id is None:
            return self._stop(
                context, action, authorization, status="blocked",
                code=SecurityDecisionCode.BLOCK, reasons=["POLICY_VIOLATION"],
                rules=["active-authorization-requires-freeze-id"],
                message="授权缺少冻结编号，不能释放。",
                evidence_refs=evidence,
            )
        try:
            view = self.freeze_reader(self._trusted(context), authorization.freeze_id)
        except Exception:
            view = None
        if view is None or isinstance(view, QueryFailure):
            failure = view if isinstance(view, QueryFailure) else None
            if failure is not None and failure.error.code == "RECORD_NOT_FOUND":
                try:
                    authorization = _update(
                        self.state, context,
                        authorization.model_copy(update={"status": "invalid"}),
                    )
                except SecurityError:
                    pass
                return self._stop(
                    context, action, authorization, status="blocked",
                    code=SecurityDecisionCode.BLOCK, reasons=["FREEZE_NOT_FOUND"],
                    rules=["vanished-freeze-invalidates-authorization"],
                    message="冻结记录不存在，授权已失效。",
                    evidence_refs=evidence,
                )
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["DEPENDENCY_UNAVAILABLE"],
                rules=["bank-facts-required-before-release"],
                message="暂无法核对冻结余额，释放已暂停。",
                evidence_refs=evidence,
            )
        facts = view.data
        if facts.account_id != authorization.account_id:
            return self._stop(
                context, action, authorization, status="blocked",
                code=SecurityDecisionCode.BLOCK, reasons=["POLICY_VIOLATION"],
                rules=["freeze-owner-must-match-authorization"],
                message="冻结归属与授权不一致，不能释放。",
                evidence_refs=evidence,
            )
        remaining = facts.remaining_fen
        consumed = facts.captured_total_fen
        if remaining == 0:
            try:
                authorization = _update(
                    self.state, context,
                    authorization.model_copy(update={"status": "completed"}),
                )
            except SecurityError as exc:
                return self._stop(
                    context, action, authorization, status="needs_attention",
                    code=SecurityDecisionCode.PAUSE, reasons=[exc.code],
                    rules=["release-state-write-required"],
                    message="结束状态暂不可记录，保留待处理。",
                    evidence_refs=evidence,
                )
            return self._stop(
                context, action, authorization, status="nothing_to_release",
                code=SecurityDecisionCode.BLOCK, reasons=["ZERO_REMAINING_NO_RELEASE"],
                rules=["zero-remaining-no-release"],
                message=(
                    f"冻结余额为零，无需释放：已消费 {_yuan(facts.captured_total_fen)}，"
                    f"已释放 {_yuan(facts.released_total_fen)}，仍冻结 {_yuan(remaining)}。"
                ),
                remaining_fen=remaining,
                consumed_total_fen=facts.captured_total_fen,
                evidence_refs=evidence,
            )
        if remaining > authorization.max_amount_fen:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["POLICY_VIOLATION"],
                rules=["bank-facts-exceed-authorization"],
                message="银行余额超过确认金额，暂不释放。",
                evidence_refs=evidence,
            )

        # Authorization snapshot and decision must persist before the bank call.
        operation_id = self.operation_factory()
        action = self._release_action(authorization, authorization.freeze_id, remaining)
        submit_context = context.model_copy(update={
            "operation_id": operation_id, "action_revision": 1,
        })
        try:
            snapshot_ref = self.snapshot_writer(submit_context, None, (), self.clock())
            if not snapshot_ref:
                raise ValueError("empty authorization snapshot reference")
        except Exception:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["AUDIT_UNAVAILABLE"],
                rules=["authorization-snapshot-required"],
                message="授权记录暂不可用，释放已暂停。",
                evidence_refs=evidence,
            )
        decision = self._decision(
            submit_context, action, operation_id=operation_id,
            decision=SecurityDecisionCode.ALLOW, reasons=["SECURITY_CHECK_PASSED"],
            rules=[
                "limited-release-authorized",
                "original-confirmation-bound",
                "in-flight-verified-before-release",
            ],
            message="已按限定授权准备释放未消费冻结余额。",
            snapshot_ref=snapshot_ref, risk=RiskLevel.LOW,
        )
        try:
            self.decision_sink(decision)
        except Exception:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE, reasons=["AUDIT_UNAVAILABLE"],
                rules=["audit-before-release"],
                message="安全记录暂不可用，释放已暂停。",
                evidence_refs=evidence,
            )
        try:
            _, created = self.state.claim_release_execution(
                submit_context, action, decision,
            )
        except ValueError as exc:
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE,
                reasons=[getattr(exc, "code", "DEPENDENCY_UNAVAILABLE")],
                rules=["release-claim-required-before-bank"],
                message="释放编号暂不可记录，已停止提交。",
                evidence_refs=evidence,
            )
        if not created:
            return self._recover(
                context, authorization, operation_id,
            )
        result = self.bank_release(
            self._trusted(submit_context), operation_id,
            ReleaseFrozenInput(freeze_id=authorization.freeze_id,
                               amount_fen=remaining),
        )
        if isinstance(result, QueryFailure):
            try:
                self.state.record_execution(
                    submit_context, action, "unknown", None,
                )
            except ValueError:
                pass
            return self._stop(
                context, action, authorization, status="needs_attention",
                code=SecurityDecisionCode.PAUSE,
                reasons=[result.error.code],
                rules=["release-unknown-keep-original-id"],
                message="释放结果未知，保留原编号待核实。",
                operation_id=operation_id, evidence_refs=evidence,
            )
        if result.operation_status == "succeeded":
            receipt = result.receipt
            try:
                self.state.record_execution(
                    submit_context, action, "completed", str(operation_id),
                )
                authorization = _update(
                    self.state, context,
                    authorization.model_copy(update={"status": "completed"}),
                )
            except ValueError as exc:
                return self._stop(
                    context, action, authorization, status="needs_attention",
                    code=SecurityDecisionCode.PAUSE,
                    reasons=[getattr(exc, "code", "DEPENDENCY_UNAVAILABLE")],
                    rules=["release-state-write-required"],
                    message="释放已提交，状态暂不可记录，保留待处理。",
                    operation_id=operation_id,
                    released_amount_fen=(receipt.released_amount_fen if receipt else None),
                    evidence_refs=evidence,
                )
            released_fen = receipt.released_amount_fen if receipt else None
            receipt_remaining = receipt.remaining_fen if receipt else None
            message = "没花完的钱已退回原卡。"
            if receipt is not None:
                message = f"没花完的 {_yuan(receipt.released_amount_fen)}已退回原卡。"
            return self._stop(
                context, action, authorization, status="released",
                code=SecurityDecisionCode.ALLOW, reasons=["SECURITY_CHECK_PASSED"],
                rules=["limited-release-submitted-exact-remainder"],
                message=message,
                operation_id=operation_id,
                released_amount_fen=released_fen,
                remaining_fen=receipt_remaining,
                consumed_total_fen=consumed,
                snapshot_ref=snapshot_ref, risk=RiskLevel.LOW,
                evidence_refs=evidence + [str(operation_id)],
            )
        try:
            self.state.record_execution(
                submit_context, action, "completed", str(operation_id),
            )
        except ValueError:
            pass
        return self._stop(
            context, action, authorization, status="needs_attention",
            code=SecurityDecisionCode.PAUSE, reasons=["RELEASE_FAILED"],
            rules=["release-failed-keeps-original-id"],
            message="释放未成功，保留原编号待处理。",
            operation_id=operation_id, evidence_refs=evidence + [str(operation_id)],
        )
