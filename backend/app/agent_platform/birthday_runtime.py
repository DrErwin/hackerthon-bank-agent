"""Real birthday ports: the security gate, bank gateway and the §3.5 release.

v05-cross-platform/09 assembly. The cross module only orchestrates; every money
touch lives here: each write goes through the per-task SecurityGate (a
clause-bearing freeze confirmation, then the MEDIUM step-up verification the
platform resumes after), the deterministic executor claims it once, and the
gateway submits only under the #272 live-claim authorizer. The limited ending
releases the bank-verified remainder through the original freeze operation.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID, uuid4

from app.contracts.bank import (
    CaptureFrozenInput, CreateOrderInput, DeliveryInput, FreezeFundsInput,
    ListProductsInput, OperationResult, QueryFailure, QueryOk,
)
from app.contracts.common import (
    Category, DisplayField, OperationStatus, Phase, SecurityDecisionCode, TaskStatus,
)

_TERMINAL = {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED,
             TaskStatus.PARTIALLY_SUCCEEDED}
from app.contracts.platform import TrustedContext
from app.contracts.audit import AuthorizationSnapshot
from app.contracts.security import (
    ActionDescriptor, SecurityDecision, VerificationSummary,
)
from app.modules.cross.birthday_ports import (
    GateAnswer, ReleaseOutcome as PortsRelease, WriteOutcome as PortsWrite,
)
from app.security import SecurityGate, ToolRegistry
from app.security.birthday_policy import BIRTHDAY_TOOLS, BirthdaySecurityPolicy
from app.security.birthday_release import (
    LimitedReleaseFinalizer, authorize_birthday_write, bind_freeze_result,
    grant_release_authorization,
)
from app.security.gate import DeterministicExecutor, SecurityError
from app.security.state import SQLiteSecurityState


def _yuan(fen) -> str:
    return f"{(fen or 0) / 100:.2f}"


_ACTION_LABELS = {
    "bank.freeze_funds": "冻结生日资金",
    "bank.create_order": "创建生日订单",
    "bank.capture_frozen": "从冻结资金付款",
}


def _display_fields(action_name: str, parameters: dict) -> list[DisplayField]:
    from app.security.birthday_policy import with_release_clause

    fields = [DisplayField(name="action", label="办理事项",
                           value_text=_ACTION_LABELS.get(action_name, action_name))]
    if "amount_fen" in parameters:
        fields.append(DisplayField(name="amount", label="金额",
                                   value_text=f"{_yuan(parameters['amount_fen'])} 元"))
    if "product_id" in parameters:
        fields.append(DisplayField(
            name="item", label="商品",
            value_text=f"{parameters.get('merchant_name', '')}·{parameters.get('purpose', '')}",
        ))
    if action_name == "bank.freeze_funds":
        return with_release_clause(fields)
    return fields


class BirthdayRuntime:
    """Owns the shared security state and builds one ports set per task."""

    def __init__(self, runtime, *, demo_user_id: str, current_demo_round: Callable[[], str]):
        self.runtime = runtime
        # One state store with the shared confirmation service: claims, the
        # §3.5 release authorizations and the gateway authorizer all read it.
        self.state: SQLiteSecurityState = runtime.confirmations.state
        self.policy = BirthdaySecurityPolicy(
            demo_user_id=demo_user_id, current_demo_round=current_demo_round,
        )
        self.authorize_birthday = authorize_birthday_write(self.state)
        self.current_demo_round = current_demo_round

    def ports_factory(self, _trusted):
        """``register_cross`` calls this per advance; every ports method takes
        the real caller context, so the factory argument stays unused."""

        return BirthdayTaskPorts(self)


class BirthdayTaskPorts:
    def __init__(self, wiring: BirthdayRuntime):
        self.wiring = wiring
        self.runtime = wiring.runtime

    # ----------------------------------------------------------- plumbing

    def _trace(self, trusted):
        task = self.runtime.application.get_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id)
        from .harness import RunTrace

        return RunTrace(self.runtime.audit, trusted, task.checkpoint_thread_id,
                        task.snapshot["trace_id"])

    def _actions(self, trusted) -> dict:
        task = self.runtime.application.get_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
        )
        return (task.snapshot or {}).get("birthday_actions") or {}

    def _remember(self, trusted, key: str, action: dict) -> None:
        task = self.runtime.application.get_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
        )
        stored = (task.snapshot or {}).get("birthday_actions") or {}
        actions = {**stored, key: action}
        self.runtime.application.update_task(
            trusted.user_id, trusted.demo_round_id, trusted.task_id,
            task.revision, task.run_id, task.status, task.checkpoint_id,
            {**task.snapshot, "birthday_actions": actions},
        )

    def _action(self, trusted, key: str, parameters: dict) -> dict:
        action = self._actions(trusted).get(key)
        if action is not None and action["parameters"] == parameters:
            return action
        # Sequential writes of one action need a strictly rising revision
        # (the state layer refuses a stale one); count from the highest ever
        # used so a replaced entry never rewinds the counter.
        revision = 1 + max(
            (stored.get("action_revision", 0)
             for stored in self._actions(trusted).values()
             if stored.get("parameters", {}).get("__action__")
             == parameters["__action__"]),
            default=0,
        )
        action = {"operation_id": str(uuid4()), "parameters": parameters,
                  "action_revision": revision}
        self._remember(trusted, key, action)
        return action

    def _parameters_for(self, trusted, operation_ref: str) -> dict:
        for stored in self._actions(trusted).values():
            if stored.get("operation_id") == operation_ref:
                return stored.get("parameters") or {}
        return {}

    def _freeze_id(self, trusted) -> str | None:
        freeze = self._actions(trusted).get("freeze") or {}
        operation_id = freeze.get("operation_id")
        if not operation_id:
            return None
        lookup = self.runtime.gateway.get_operation(trusted, UUID(operation_id))
        if isinstance(lookup, QueryFailure) or lookup.lookup == "not_found":
            return None
        operation = lookup.operation
        if operation.operation_status is OperationStatus.SUCCEEDED and operation.receipt:
            return operation.receipt.freeze_id
        return None

    def _gate(self, trusted):
        runtime = self.runtime
        registry = ToolRegistry()

        def freeze_handler(context, payload):
            return runtime.gateway.freeze_funds(_trusted_of(context),
                UUID(payload["operation_id"]), FreezeFundsInput(
                    account_id=payload["account_id"], amount_fen=payload["amount_fen"],
                    reason=payload["reason"]))

        def order_handler(context, payload):
            request = CreateOrderInput.model_validate(payload["request"])
            return runtime.gateway.create_order(_trusted_of(context),
                                                UUID(payload["operation_id"]), request)

        def capture_handler(context, payload):
            freeze_id = self._freeze_id(_trusted_of(context))
            if freeze_id is None:
                raise ValueError("FREEZE_NOT_RESOLVED")
            request = CaptureFrozenInput(
                freeze_id=freeze_id, amount_fen=payload["amount_fen"],
                merchant_id=payload["merchant_id"], merchant_name=payload["merchant_name"],
                purpose=payload["purpose"], category=Category(payload.get("category", "shopping")),
                order_id=payload.get("order_id"),
            )
            return runtime.gateway.capture_frozen(_trusted_of(context),
                                                  UUID(payload["operation_id"]), request)

        handlers = {"bank.freeze_funds": freeze_handler,
                    "bank.create_order": order_handler,
                    "bank.capture_frozen": capture_handler}
        for declaration in BIRTHDAY_TOOLS:
            if declaration.name in handlers:
                registry.register(declaration, handlers[declaration.name])

        pending_snapshots: dict[str, AuthorizationSnapshot] = {}

        def write_snapshot(context, confirmation, verifications, captured_at):
            from app.contracts.audit import (
                AuthorizationConfirmation, AuthorizationVerification,
            )

            ref = str(uuid4())
            pending_snapshots[ref] = AuthorizationSnapshot(
                user_id=context.user_id, session_id=context.session_id,
                demo_round_id=context.demo_round_id, task_id=context.task_id,
                operation_id=context.operation_id,
                action_revision=context.action_revision,
                confirmation=AuthorizationConfirmation(
                    confirmation_id=confirmation.confirmation_id,
                    version=confirmation.confirmation_version,
                    decision=confirmation.decision, decided_at=confirmation.decided_at,
                    display_fields=confirmation.display_fields,
                ) if confirmation is not None else None,
                verifications=[AuthorizationVerification(
                    verification_id=item.verification_id, scope=item.scope,
                    methods=item.methods, verified_at=item.verified_at,
                    operation_id=item.operation_id,
                    action_revision=item.action_revision,
                ) for item in verifications],
                release_authorization_id=context.release_authorization_id,
                captured_at=captured_at,
            )
            return ref

        def record_decision(decision: SecurityDecision):
            from app.contracts.audit import SecurityDecidedPayload

            ref = decision.authorization_snapshot_ref
            snapshot = pending_snapshots.pop(ref, None) if ref else None
            # The journal also requires the action parameters themselves as
            # evidence next to the authorization snapshot (transfer pattern).
            parameters = self._parameters_for(trusted, decision.parameters_ref)
            self._trace(trusted).record(
                "security.decided", SecurityDecidedPayload(decision=decision),
                "succeeded" if decision.decision is SecurityDecisionCode.ALLOW else "denied",
                evidence=snapshot, evidence_id=ref, module="security",
                snapshots={decision.parameters_ref: parameters} if parameters else None,
            )

        def confirmation_preparer(context, action):
            parameters = self._parameters_for(trusted, action.parameters_ref)
            record = runtime.confirmations.create(
                context, action, _display_fields(action.action_name, parameters))
            runtime.application.bind_ref(context.user_id, context.demo_round_id,
                                         context.task_id, "confirmation",
                                         record.confirmation_id)
            # The shared fact store is how answer_confirmation and the
            # security context find the current record (subscription pattern).
            runtime.facts.set_confirmation(record)
            return record

        def verification_preparer(context, action, confirmation, risk):
            parameters = self._parameters_for(trusted, action.parameters_ref)
            summary = VerificationSummary(
                operation_id=context.operation_id, action_revision=context.action_revision,
                source_confirmation_id=confirmation.confirmation_id,
                source_confirmation_version=confirmation.confirmation_version,
                action_name=action.action_name, amount_fen=parameters.get("amount_fen"),
                payee=None,
                display_fields=_display_fields(action.action_name, parameters),
            )
            challenge = runtime.gateway.create_verification(
                _trusted_of(context), "action_step_up", context.operation_id,
                context.action_revision, summary,
            )
            runtime.application.bind_ref(context.user_id, context.demo_round_id,
                                         context.task_id, "verification",
                                         challenge.challenge_id)
            return challenge

        def resolve_verification(context, verification_id):
            if not runtime.application.has_ref(
                context.user_id, context.demo_round_id, context.task_id,
                "verification", verification_id,
            ):
                raise SecurityError("ACCESS_DENIED")
            try:
                return runtime.gateway.get_verification_record(
                    _trusted_of(context), verification_id)
            except ValueError as exc:
                raise SecurityError("ACCESS_DENIED") from exc

        def validate_summary(context, action, confirmation, summary):
            parameters = self._parameters_for(trusted, action.parameters_ref)
            fields = _display_fields(action.action_name, parameters)
            return (summary.amount_fen == parameters.get("amount_fen")
                    and summary.payee is None
                    and summary.display_fields == fields
                    and confirmation.display_fields == fields)

        gate = SecurityGate(
            registry, runtime.confirmations,
            scope_authorizer=self.wiring.policy.authorize_tool,
            task_state_resolver=runtime._task_terminated,
            risk_assessor=self.wiring.policy.assess_risk,
            confirmation_preparer=confirmation_preparer,
            verification_preparer=verification_preparer,
            verification_resolver=resolve_verification,
            challenge_resolver=lambda context, challenge_id: runtime.gateway.get_verification(
                _trusted_of(context), challenge_id),
            decision_sink=record_decision, snapshot_writer=write_snapshot,
            summary_validator=validate_summary,
        )

        def parameter_resolver(context, action):
            parameters = self._parameters_for(trusted, action.parameters_ref)
            return {"operation_id": action.parameters_ref, **parameters}

        def operation_lookup(context, action):
            from app.security.gate import OperationObservation

            response = runtime.gateway.get_operation(
                _trusted_of(context), context.operation_id)
            if isinstance(response, QueryFailure):
                raise ValueError(response.error.code)
            if response.lookup == "not_found":
                return OperationObservation(
                    operation_id=context.operation_id, state="not_found",
                    result=None, result_ref=None)
            operation = response.operation
            terminal = operation.operation_status in (
                OperationStatus.SUCCEEDED, OperationStatus.FAILED)
            return OperationObservation(
                operation_id=operation.operation_id,
                state="completed" if terminal else "processing",
                result=operation, result_ref=str(operation.operation_id)
                if terminal else None,
            )

        def observe(result):
            from app.security.gate import OperationObservation

            if isinstance(result, QueryFailure):
                raise ValueError(result.error.code)
            if not isinstance(result, OperationResult):
                raise ValueError("unexpected bank result")
            return OperationObservation(
                operation_id=result.operation_id, state="completed",
                result=result, result_ref=str(result.operation_id))

        executor = DeterministicExecutor(
            gate, parameter_resolver=parameter_resolver,
            operation_lookup=operation_lookup, result_observer=observe,
        )
        return gate, executor

    def _security_context(self, trusted, operation_id, *, release_authorization_id=None):
        revision = 1
        for stored in self._actions(trusted).values():
            if stored.get("operation_id") == operation_id:
                revision = stored.get("action_revision", 1)
        base = self.runtime._context(trusted, UUID(operation_id), revision)
        return base.model_copy(update={
            "release_authorization_id": release_authorization_id,
        })

    # ------------------------------------------------------------ ports API

    def products(self, context, request: ListProductsInput):
        return QueryOk(kind="ok", data=self.runtime.gateway.list_products(
            context, merchant_id=request.merchant_id, purpose=request.purpose,
            deliver_by=request.deliver_by,
        ))

    def _check(self, context, key, parameters) -> GateAnswer:
        action = self._action(context, key, parameters)
        gate, _executor = self._gate(context)
        descriptor = ActionDescriptor(
            action_name=parameters["__action__"], parameters_ref=action["operation_id"],
            resource_refs=[], phase=Phase.EXECUTION,
        )
        decision = gate.check_action(
            self._security_context(context, action["operation_id"]), descriptor)
        if decision.decision in (SecurityDecisionCode.REQUIRE_CONFIRMATION,
                                 SecurityDecisionCode.REQUIRE_VERIFICATION):
            return GateAnswer(decision.decision, action["operation_id"],
                              interaction=decision.interaction)
        if decision.decision is SecurityDecisionCode.ALLOW:
            return GateAnswer(SecurityDecisionCode.ALLOW, action["operation_id"])
        return GateAnswer(decision.decision, action["operation_id"],
                          reason_code=decision.reason_codes[0] if decision.reason_codes
                          else "SECURITY_NOT_ALLOWED")

    def _execute(self, context, key, parameters) -> PortsWrite:
        action = self._actions(context).get(key)
        if action is None or action.get("parameters") != parameters:
            # An unknown or changed target is never resubmitted blind.
            return PortsWrite(executed=False, state="failed", result=None,
                              operation_id=None)
        gate, executor = self._gate(context)
        descriptor = ActionDescriptor(
            action_name=parameters["__action__"], parameters_ref=action["operation_id"],
            resource_refs=[], phase=Phase.EXECUTION,
        )
        outcome = executor.execute(
            self._security_context(context, action["operation_id"]), descriptor)
        if outcome.decision is not None and (
            outcome.decision.decision is SecurityDecisionCode.REQUIRE_VERIFICATION
        ):
            return PortsWrite(executed=False, state="verify_wait", result=None,
                              operation_id=None, verify=outcome.decision.interaction)
        result = outcome.result
        if isinstance(result, OperationResult):
            state = "completed" if result.operation_status is OperationStatus.SUCCEEDED \
                else "failed"
            return PortsWrite(executed=True, state=state, result=result,
                              operation_id=str(result.operation_id))
        if outcome.state == "unknown":
            return PortsWrite(executed=True, state="unknown", result=None,
                              operation_id=action["operation_id"])
        return PortsWrite(executed=False, state="failed", result=None,
                          operation_id=action["operation_id"])

    # --------------------------------------------------- the three writes

    _FREEZE_PARAMETERS = staticmethod(lambda plan: {
        "__action__": "bank.freeze_funds", "account_id": plan.payer_account_id,
        "amount_fen": plan.freeze_amount_fen, "reason": "生日安排",
    })

    def freeze_check(self, context, plan):
        return self._check(context, "freeze", self._FREEZE_PARAMETERS(plan))

    def freeze_execute(self, context, plan):
        return self._execute(context, "freeze", self._FREEZE_PARAMETERS(plan))

    def _order_request(self, context, plan, item):
        detail = self.runtime.application.get_controlled_detail(
            context.user_id, context.demo_round_id, plan.delivery_ref,
        )
        if detail is None:
            return None
        deliver_by = plan.deliver_by
        if len(deliver_by) == 10:  # a bare date means end of that day, Beijing time
            deliver_by += "T23:59:59+08:00"
        return CreateOrderInput(
            product_id=item["product_id"], quantity=1,
            expected_total_fen=item["amount_fen"],
            delivery=DeliveryInput(
                recipient_name=detail.payload["recipient_name"],
                phone=detail.payload["phone"], address=detail.payload["address"],
                deliver_by=deliver_by,
            ),
        )

    @staticmethod
    def _enriched(plan, item) -> dict:
        """The flow's order rows carry ids and amounts; the merchant facts
        travel on the plan items (the bank's own product cache)."""
        source = next((row for row in plan.items
                       if row.get("product_id") == item["product_id"]), {})
        return {**source, **{k: v for k, v in item.items() if v is not None}}

    def _order_parameters(self, context, plan, item) -> dict | None:
        item = self._enriched(plan, item)
        request = self._order_request(context, plan, item)
        if request is None:
            return None
        return {"__action__": "bank.create_order", "product_id": item["product_id"],
                "amount_fen": item["amount_fen"],
                "merchant_id": item["merchant_id"],
                "merchant_name": item["merchant_name"], "purpose": item["name"],
                "category": item.get("category", "shopping"),
                "request": request.model_dump(mode="json")}

    def order_check(self, context, plan, item):
        parameters = self._order_parameters(context, plan, item)
        if parameters is None:
            return GateAnswer(SecurityDecisionCode.BLOCK, str(uuid4()),
                              reason_code="DELIVERY_REFERENCE_INVALID")
        return self._check(context, f"order:{item['product_id']}", parameters)

    def order_execute(self, context, plan, item):
        parameters = self._order_parameters(context, plan, item)
        if parameters is None:
            return PortsWrite(executed=False, state="failed", result=None,
                              operation_id=None)
        return self._execute(context, f"order:{item['product_id']}", parameters)

    def _capture_parameters(self, context, plan, item, order_id) -> dict:
        item = self._enriched(plan, item)
        return {"__action__": "bank.capture_frozen", "amount_fen": item["amount_fen"],
                "merchant_id": item["merchant_id"],
                "merchant_name": item["merchant_name"],
                "purpose": item["name"], "category": item.get("category", "shopping"),
                "order_id": order_id}

    def capture_check(self, context, plan, item, order_id):
        return self._check(context, f"capture:{item['product_id']}",
                           self._capture_parameters(context, plan, item, order_id))

    def capture_execute(self, context, plan, item, order_id):
        return self._execute(context, f"capture:{item['product_id']}",
                             self._capture_parameters(context, plan, item, order_id))

    # ------------------------------------------------------- §3.5 release

    def grant_release(self, context, plan, confirmation_ref) -> str:
        freeze = self._actions(context).get("freeze") or {}
        record = self.runtime.confirmations.get(
            self._security_context(context, freeze["operation_id"]), confirmation_ref)
        authorization = grant_release_authorization(
            self.wiring.state,
            self._security_context(context, freeze["operation_id"]), record,
            account_id=plan.payer_account_id, amount_fen=plan.freeze_amount_fen,
            now=self.runtime.gateway._bank.clock(),
        )
        task = self.runtime.application.get_task(
            context.user_id, context.demo_round_id, context.task_id)
        self.runtime.application.update_task(
            context.user_id, context.demo_round_id, context.task_id,
            task.revision, task.run_id, task.status, task.checkpoint_id,
            {**task.snapshot, "birthday_release": authorization.release_authorization_id},
        )
        return authorization.release_authorization_id

    def _release_id(self, context) -> str | None:
        task = self.runtime.application.get_task(
            context.user_id, context.demo_round_id, context.task_id)
        return (task.snapshot or {}).get("birthday_release")

    def bind_freeze(self, context, plan, operation_id):
        release_id = self._release_id(context)
        if release_id is None:
            return None
        # Resolve the executor's original claim too: a bank-only lookup leaves
        # it unknown, so the limited finalizer correctly refuses to release.
        if self.requery(context, plan, "freeze", operation_id) is None:
            return None
        authorization = bind_freeze_result(
            self.wiring.state,
            self._security_context(context, operation_id), release_id,
            self.runtime.gateway.get_operation(context, UUID(operation_id)),
            self.runtime.gateway._bank.clock(),
        )
        return authorization.freeze_id

    def requery(self, context, plan, target, operation_id):
        stored = next((action for action in self._actions(context).values()
                       if action["operation_id"] == str(operation_id)), None)
        if stored is None:
            return None
        descriptor = ActionDescriptor(
            action_name=stored["parameters"]["__action__"],
            parameters_ref=stored["operation_id"], resource_refs=[], phase=Phase.EXECUTION)
        security_context = self._security_context(context, stored["operation_id"])
        # Query only an already claimed operation. Never let a missing claim
        # turn a recovery request into a fresh write through execute().
        if self.wiring.state.get_execution(security_context, descriptor) is None:
            return None
        _gate, executor = self._gate(context)
        outcome = executor.execute(security_context, descriptor)
        operation = outcome.result
        if (isinstance(operation, OperationResult)
                and operation.operation_status in (OperationStatus.SUCCEEDED, OperationStatus.FAILED)):
            state = "completed" if operation.operation_status is OperationStatus.SUCCEEDED \
                else "failed"
            return PortsWrite(executed=True, state=state, result=operation,
                              operation_id=str(operation_id))
        return None

    def finalize(self, context, plan, reason):
        # The §3.5 gate only releases for an ended task; the orchestrator
        # calls finalize from inside its own ending, so the durable task
        # status is settled here first (the caller rewrites the exact final
        # status from the flow's own result afterwards). In-flight, owner
        # and round checks still apply inside the finalizer.
        conservative = {"user_cancelled": TaskStatus.CANCELLED,
                        "business_failure": TaskStatus.FAILED}.get(
                            reason, TaskStatus.FAILED)
        task = self.runtime.application.get_task(
            context.user_id, context.demo_round_id, context.task_id)
        if task.status not in _TERMINAL:
            self.runtime.application.update_task(
                context.user_id, context.demo_round_id, context.task_id,
                task.revision, task.run_id, conservative, task.checkpoint_id,
                task.snapshot,
            )
        release_id = self._release_id(context)
        freeze = self._actions(context).get("freeze") or {}
        freeze_operation = freeze.get("operation_id") or str(uuid4())
        security_context = self._security_context(
            context, freeze_operation, release_authorization_id=release_id)

        pending: dict[str, AuthorizationSnapshot] = {}

        def release_snapshot_writer(release_context, confirmation, verifications, at):
            from app.contracts.audit import (
                AuthorizationConfirmation, AuthorizationSnapshot as Snapshot,
            )

            # A release carries no confirmation of its own; the §3.5 record's
            # source (the approved clause-bearing freeze confirmation) is the
            # authorization the journal demands on a sensitive allow.
            source = None
            if confirmation is None and release_context.release_authorization_id:
                try:
                    authorization = self.wiring.state.get_release_authorization(
                        release_context, release_context.release_authorization_id)
                    freeze_operation = authorization.freeze_operation_id
                    freeze_operation = UUID(str(freeze_operation))
                    record = self.runtime.confirmations.get(
                        release_context.model_copy(update={
                            "operation_id": freeze_operation}),
                        authorization.confirmation_id)
                    source = AuthorizationConfirmation(
                        confirmation_id=record.confirmation_id,
                        version=record.confirmation_version,
                        decision=record.decision, decided_at=record.decided_at,
                        display_fields=record.display_fields,
                    )
                except Exception:
                    source = None
            ref = str(uuid4())
            pending[ref] = Snapshot(
                user_id=release_context.user_id, session_id=release_context.session_id,
                demo_round_id=release_context.demo_round_id,
                task_id=release_context.task_id,
                operation_id=release_context.operation_id,
                action_revision=release_context.action_revision,
                confirmation=source, verifications=[],
                release_authorization_id=release_context.release_authorization_id,
                captured_at=at,
            )
            return ref

        def sink(decision: SecurityDecision):
            from app.contracts.audit import SecurityDecidedPayload

            ref = decision.authorization_snapshot_ref
            snapshot = pending.pop(ref, None) if ref else None
            self._trace(context).record(
                "security.decided", SecurityDecidedPayload(decision=decision),
                "succeeded" if decision.decision is SecurityDecisionCode.ALLOW else "denied",
                evidence=snapshot, evidence_id=ref, module="security",
                snapshots={decision.parameters_ref: {"action": decision.action_name}}
                if decision.parameters_ref else None,
            )

        finalizer = LimitedReleaseFinalizer(
            self.wiring.state,
            decision_sink=sink,
            snapshot_writer=release_snapshot_writer,
            task_state_resolver=self.runtime._task_terminated,
            freeze_reader=lambda trusted, freeze_id:
                self.runtime.gateway.get_freeze(trusted, freeze_id),
            operation_reader=lambda trusted, operation_id:
                self.runtime.gateway.get_operation(trusted, operation_id),
            bank_release=lambda trusted, operation_id, request:
                self.runtime.gateway.release_frozen(trusted, operation_id, request),
            clock=self.runtime.gateway._bank.clock,
            current_demo_round=self.wiring.current_demo_round,
        )
        outcome = finalizer.finalize(security_context, reason)
        return PortsRelease(
            status=outcome.status,
            released_amount_fen=outcome.released_amount_fen,
            remaining_fen=outcome.remaining_fen,
            consumed_total_fen=outcome.consumed_total_fen,
            release_operation_id=str(outcome.release_operation_id)
            if outcome.release_operation_id else None,
            message=outcome.decision.message,
        )


def _trusted_of(context):
    return TrustedContext(
        user_id=context.user_id, session_id=context.session_id,
        demo_round_id=context.demo_round_id, task_id=context.task_id,
        run_id=context.run_id, parent_task_id=context.source_task_id,
    )
