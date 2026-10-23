"""Cross-module public models: start input, constraints, arrangements and the task view.

Contract §5.4 plus the 2026-10-24 v05-cross-platform/01 revision. The models check
shapes and invariants that hold without runtime facts; permission, bank balances
and adoption truth stay with the server (ticket 01 boundary).
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .bank import PayeeInput
from .bills import BillScope
from .common import (
    ContractModel, ID, Money, OperationId, PositiveInt, RequestId, SignedMoney, TaskStatus, Timestamp,
)
from .tasks import ModuleError


class CrossScenario(StrEnum):
    """Old names keep their old meaning; the two new entries express the new life goals."""

    MONTHLY_ARRANGEMENT = "monthly_arrangement"
    EXPENSE_REDUCTION = "expense_reduction"
    BIRTHDAY = "birthday"
    BUDGET = "budget"
    INCOME_DISTRIBUTION = "income_distribution"


FundsBasis = Literal["available_balance", "selected_income"]
ArrangementStatus = Literal["active", "superseded", "closed"]
BudgetStatus = Literal["active", "superseded"]
CommitmentState = Literal["pending", "active", "unknown", "closed"]
StopReason = Literal["user_cancelled", "security_blocked", "business_failure"]

RatioBps = Annotated[int, Field(strict=True, ge=1, le=10000)]


class BudgetRef(ContractModel):
    budget_id: ID
    version: PositiveInt


class BudgetView(ContractModel):
    """Personal spending budget view (§5.4); adopted is server-decided, never model-filled."""

    budget_ref: BudgetRef | None
    purpose: str
    scope: BillScope
    personal_limit_fen: Money
    used_fen: SignedMoney
    remaining_fen: SignedMoney
    facts_as_of: Timestamp
    adopted: bool

    @model_validator(mode="after")
    def match_remaining_and_adoption(self) -> "BudgetView":
        if self.remaining_fen != self.personal_limit_fen - self.used_fen:
            raise ValueError("remaining_fen must equal personal_limit_fen minus used_fen")
        if self.adopted and self.budget_ref is None:
            raise ValueError("an adopted budget carries its budget_ref")
        if not self.adopted and self.budget_ref is not None:
            raise ValueError("an unadopted budget view carries no budget_ref yet")
        return self


class AdoptedBudget(ContractModel):
    """Server-saved adoption record; a business constraint, not an execution authorization."""

    budget_id: ID
    user_id: ID
    demo_round_id: ID
    source_task_id: ID
    version: PositiveInt
    scope: BillScope
    purpose: str
    personal_limit_fen: Money
    adopted_at: Timestamp
    adoption_interaction_id: ID
    status: BudgetStatus


class BudgetCommitment(ContractModel):
    """One in-flight occupation against a budget; deterministic code updates it (§5.4)."""

    budget_ref: BudgetRef
    task_id: ID
    commitment_id: ID
    committed_fen: Money
    unconsumed_fen: Money
    freeze_id: ID | None
    operation_ids: list[OperationId]
    settled_transaction_ids: list[ID]
    state: CommitmentState
    updated_at: Timestamp

    @model_validator(mode="after")
    def no_double_counted_or_duplicated_references(self) -> "BudgetCommitment":
        if self.unconsumed_fen > self.committed_fen:
            raise ValueError("unconsumed occupation cannot exceed the committed amount")
        if len(set(self.operation_ids)) != len(self.operation_ids):
            raise ValueError("operation_ids must not repeat")
        if len(set(self.settled_transaction_ids)) != len(self.settled_transaction_ids):
            raise ValueError("settled_transaction_ids must not repeat")
        return self


class Allocation(ContractModel):
    """One allocation candidate; ratio conversion and final amounts are computed by code."""

    destination: Literal["transfer", "retain"]
    target_account_id: ID | None = None
    payee: PayeeInput | None = None
    amount_fen: Money | None = None
    ratio_bps: RatioBps | None = None

    @model_validator(mode="after")
    def match_amount_and_target_to_destination(self) -> "Allocation":
        if (self.amount_fen is None) == (self.ratio_bps is None):
            raise ValueError("exactly one of amount_fen or ratio_bps is required")
        if self.destination == "transfer":
            if (self.target_account_id is None) == (self.payee is None):
                raise ValueError("transfer needs exactly one of target_account_id or payee")
            if self.amount_fen is not None and self.amount_fen <= 0:
                raise ValueError("a transfer amount must be greater than zero")
        elif self.target_account_id is not None or self.payee is not None:
            raise ValueError("retain leaves the funds in the payer account and takes no payee")
        return self


class CrossConstraints(ContractModel):
    """Flat constraint candidates across scenarios; all optional, server fills no defaults."""

    # birthday
    recipient_hint: str | None = None
    recipient_ref: ID | None = None
    birthday_on: date | None = None
    deliver_by: Timestamp | None = None
    delivery_ref: ID | None = None
    budget_fen: Money | None = None
    budget_ref: BudgetRef | None = None
    preferences: list[str] | None = None
    # personal budget
    scope: BillScope | None = None
    personal_limit_fen: Money | None = None
    purpose: str | None = None
    # income distribution / monthly arrangement
    payer_account_id: ID | None = None
    income_transaction_ids: list[ID] | None = None
    income_hint: str | None = None
    allocation_rule_ref: ID | None = None
    allocations: list[Allocation] | None = None
    funds_basis: FundsBasis | None = None
    arrangement_amount_fen: Money | None = None
    living_reserve_fen: Money | None = None
    reserve_includes_known_debits: bool | None = None
    upcoming_debit_scope: BillScope | None = None
    # expense reduction
    comparison_scope: BillScope | None = None
    selected_subscription_ids: list[ID] | None = None

    @model_validator(mode="after")
    def reject_contradictory_funds_scope_and_duplicates(self) -> "CrossConstraints":
        if self.income_transaction_ids is not None and (
            len(set(self.income_transaction_ids)) != len(self.income_transaction_ids)
        ):
            raise ValueError("income_transaction_ids must not repeat")
        if self.selected_subscription_ids is not None and (
            len(set(self.selected_subscription_ids)) != len(self.selected_subscription_ids)
        ):
            raise ValueError("selected_subscription_ids must not repeat")
        if self.funds_basis == "available_balance" and self.income_transaction_ids:
            raise ValueError("available_balance contradicts income_transaction_ids; clarify instead")
        return self


class CrossStartInput(ContractModel):
    """cross.start_task input (§5.4); the module identifies or clarifies the scenario."""

    request_id: RequestId
    goal: str
    scenario: CrossScenario | None = None
    constraints: CrossConstraints | None = None

    @model_validator(mode="after")
    def goal_is_not_blank(self) -> "CrossStartInput":
        if not self.goal.strip():
            raise ValueError("goal must be a non-blank life goal")
        return self


class ArrangementView(ContractModel):
    """Server-generated view of one month's fund arrangement (D1/C4 fields)."""

    arrangement_id: ID
    plan_revision: PositiveInt
    payer_account_id: ID
    funds_basis: FundsBasis
    income_transaction_ids: list[ID]
    base_fen: Money
    living_reserve_fen: Money
    reserve_includes_known_debits: bool
    upcoming_debit_scope: BillScope
    known_debits_fen: Money
    protected_fen: Money
    distributable_fen: SignedMoney
    facts_as_of: Timestamp
    adopted: bool

    @model_validator(mode="after")
    def match_reserve_and_distribution_equations(self) -> "ArrangementView":
        if len(set(self.income_transaction_ids)) != len(self.income_transaction_ids):
            raise ValueError("income_transaction_ids must not repeat")
        if self.funds_basis == "selected_income" and not self.income_transaction_ids:
            raise ValueError("selected_income lists its verified source transactions")
        if self.funds_basis == "available_balance" and self.income_transaction_ids:
            raise ValueError("available_balance carries no income transaction ids")
        expected_protected = self.living_reserve_fen + (
            0 if self.reserve_includes_known_debits else self.known_debits_fen
        )
        if self.protected_fen != expected_protected:
            raise ValueError("protected_fen must match the living reserve and known debits")
        if self.distributable_fen != self.base_fen - self.protected_fen:
            raise ValueError("distributable_fen must equal base_fen minus protected_fen")
        return self


class AdoptedArrangement(ContractModel):
    """Server-saved adoption snapshot of one arrangement; not an execution authorization."""

    arrangement_id: ID
    user_id: ID
    demo_round_id: ID
    source_task_id: ID
    plan_revision: PositiveInt
    payer_account_id: ID
    funds_basis: FundsBasis
    income_transaction_ids: list[ID]
    base_fen: Money
    living_reserve_fen: Money
    reserve_includes_known_debits: bool
    upcoming_debit_scope: BillScope
    known_debits_fen: Money
    adopted_at: Timestamp
    adoption_interaction_id: ID
    status: ArrangementStatus

    @model_validator(mode="after")
    def match_funds_basis_to_sources(self) -> "AdoptedArrangement":
        if len(set(self.income_transaction_ids)) != len(self.income_transaction_ids):
            raise ValueError("income_transaction_ids must not repeat")
        if self.funds_basis == "selected_income" and not self.income_transaction_ids:
            raise ValueError("selected_income lists its verified source transactions")
        if self.funds_basis == "available_balance" and self.income_transaction_ids:
            raise ValueError("available_balance carries no income transaction ids")
        return self


class CrossStep(ContractModel):
    step_id: ID
    action: str
    child_task_id: ID | None = None
    operation_id: OperationId | None = None
    status: TaskStatus | None = None
    amount_fen: Money | None = None
    order_id: ID | None = None
    payment_status: Literal["unpaid", "paid"] | None = None
    result_ref: ID | None = None
    error: ModuleError | None = None
    depends_on: list[ID] = Field(default_factory=list)


class CrossTaskView(ContractModel):
    """Parent cross task view; new fields default so old payloads keep parsing."""

    scenario: CrossScenario | None = None
    plan_revision: PositiveInt
    steps: list[CrossStep]
    budget: BudgetView | None = None
    summary: str
    plan_step_ids: list[ID] | None = None
    active_step_id: ID | None = None
    interaction_task_id: ID | None = None
    arrangement: ArrangementView | None = None
    stop_reason: StopReason | None = None

    @model_validator(mode="after")
    def check_step_references_and_dependencies(self) -> "CrossTaskView":
        step_ids = [step.step_id for step in self.steps]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("step_id must be unique within the plan")

        def _no_duplicates(field_name: str, values: list[ID]) -> None:
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not repeat")

        if self.plan_step_ids is not None:
            _no_duplicates("plan_step_ids", self.plan_step_ids)
            unknown = set(self.plan_step_ids) - set(step_ids)
            if unknown:
                raise ValueError("plan_step_ids reference unknown steps")
        if self.active_step_id is not None and self.active_step_id not in step_ids:
            raise ValueError("active_step_id references an unknown step")

        depends: dict[str, list[str]] = {}
        for step in self.steps:
            _no_duplicates(f"steps[{step.step_id}].depends_on", step.depends_on)
            for dep in step.depends_on:
                if dep == step.step_id:
                    raise ValueError("a step cannot depend on itself")
                if dep not in step_ids:
                    raise ValueError("depends_on references an unknown step")
            depends[step.step_id] = list(step.depends_on)

        # A valid plan is a DAG: report the first cycle found by depth-first search.
        state = {step_id: 0 for step_id in step_ids}

        def has_cycle(node: str) -> bool:
            state[node] = 1
            for dep in depends[node]:
                if state[dep] == 1 or (state[dep] == 0 and has_cycle(dep)):
                    return True
            state[node] = 2
            return False

        if any(state[step_id] == 0 and has_cycle(step_id) for step_id in step_ids):
            raise ValueError("step dependencies form a cycle")
        return self
