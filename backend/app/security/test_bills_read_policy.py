"""Issue #137: security-owned read declarations, real gate and bank facts.

These offline checks use no model and do not certify the bills audit payload.
"""
from datetime import datetime, timezone
import sqlite3

import pytest

from app.contracts.bank import QueryFailure, QueryOk
from app.contracts.common import OperationLevel, Phase, RiskLevel
from app.contracts.platform import TrustedContext
from app.modules.bills.manifest import MANIFEST as BILLS_MANIFEST
from app.modules.bills.reads import PRIVATE_TOOLS as BILLS_PRIVATE_TOOLS
from app.security import ConfirmationService, DeterministicExecutor, SecurityGate, ToolRegistry
from app.security.demo_policy import DemoSecurityPolicy, RiskFactsUnavailable
from app.security.test_demo_policy import action_for, execution_context, make_policy
from app.services.bank_gateway.gateway import BankGateway
from app.services.mock_bank.core import MockBankService
from app.storage.mock_bank.repository import MockBankStore


def unavailable_facts(*args):
    raise AssertionError("bills reads must not depend on transfer risk fixtures")


@pytest.mark.parametrize("declaration", BILLS_PRIVATE_TOOLS, ids=lambda item: item.name)
def test_bills_reads_have_policy_provenance_without_transfer_fixtures(declaration):
    policy, _ = make_policy(unavailable_facts)
    assessment = policy.assess_risk(execution_context(), action_for(declaration.name), declaration)
    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.rule_id == "bills-own-account-read"
    assert assessment.policy_version == policy.policy_version
    assert assessment.evidence_ref == "policy:issue-137:pm-interim-20261018"


@pytest.mark.parametrize("declaration", (*BILLS_PRIVATE_TOOLS, BILLS_MANIFEST.capabilities[0]),
                         ids=lambda item: item.name)
@pytest.mark.parametrize("change", [
    {"required_permissions": []}, {"required_permissions": ["transfer.read"]},
    {"operation_level": OperationLevel.MODIFY}, {"side_effect": True},
    {"confirmation_policy": "per_action"}, {"timeout_ms": 9999},
    {"retry_policy": "none"}, {"handler_ref": "bills.other_handler"},
    {"input_schema_ref": "OtherInput"}, {"output_schema_ref": "OtherOutput"},
])
def test_every_bill_declaration_field_is_pinned(declaration, change):
    policy, _ = make_policy(unavailable_facts)
    changed = declaration.model_copy(update=change)
    if declaration.name == "bills.summarize":
        context = TrustedContext(user_id="demo-user-1", session_id="session-1", task_id="task-1",
                                 run_id="run-1", parent_task_id=None, demo_round_id="demo-round-1")
        assert not policy.authorize_capability(context, changed)
    else:
        context = execution_context()
        assert not policy.authorize_tool(context, action_for(changed.name), changed)
        with pytest.raises(RiskFactsUnavailable):
            policy.assess_risk(context, action_for(changed.name), changed)


@pytest.mark.parametrize("declaration", (*BILLS_PRIVATE_TOOLS, BILLS_MANIFEST.capabilities[0]),
                         ids=lambda item: item.name)
def test_module_mutation_cannot_mutate_the_security_allowlist(declaration, monkeypatch):
    policy, _ = make_policy(unavailable_facts)
    monkeypatch.setattr(declaration, "timeout_ms", declaration.timeout_ms + 1)
    if declaration.name == "bills.summarize":
        context = TrustedContext(user_id="demo-user-1", session_id="session-1", task_id="task-1",
                                 run_id="run-1", parent_task_id=None, demo_round_id="demo-round-1")
        assert not policy.authorize_capability(context, declaration)
    else:
        assert not policy.authorize_tool(execution_context(), action_for(declaration.name), declaration)


@pytest.mark.parametrize("changes", [{"user_id": "other-user"}, {"demo_round_id": "old-round"}])
@pytest.mark.parametrize("declaration", BILLS_PRIVATE_TOOLS, ids=lambda item: item.name)
def test_read_risk_does_not_bypass_user_or_round_scope(changes, declaration):
    policy, _ = make_policy(unavailable_facts)
    context = execution_context(**changes)
    assert not policy.authorize_tool(context, action_for(declaration.name), declaration)
    with pytest.raises(RiskFactsUnavailable):
        policy.assess_risk(context, action_for(declaration.name), declaration)


@pytest.mark.parametrize("name", ["bills.export_details", "bills.bank.submit_transfer",
                                "bills.bank.list_subscriptions"])
def test_bills_read_permission_does_not_grant_new_tools(name):
    policy, _ = make_policy(unavailable_facts)
    declaration = BILLS_PRIVATE_TOOLS[0].model_copy(update={"name": name})
    assert not policy.authorize_tool(execution_context(), action_for(name), declaration)


def test_real_gate_and_bank_keep_read_scope_and_money_unchanged(tmp_path):
    now = datetime(2026, 10, 19, tzinfo=timezone.utc)
    bank_path = tmp_path / "bank.sqlite"
    bank = MockBankService(MockBankStore(bank_path), demo_secret=b"test-only-bills-read-secret-32-bytes",
                           clock=lambda: now)
    bank.seed_flow_history()
    policy = DemoSecurityPolicy(demo_user_id="U1", admin_actor_id="admin",
                                current_demo_round=lambda: "D1", risk_facts=unavailable_facts)
    context = execution_context(user_id="U1", demo_round_id="D1")
    trusted = TrustedContext(user_id="U1", session_id=context.session_id, task_id=context.task_id,
                             run_id=context.run_id, parent_task_id=None, demo_round_id="D1")
    decisions, calls = [], []
    parameters = {"account_id": "A1"}
    stopped = [False]

    def no_sensitive_flow(*args):
        raise AssertionError("read must not prepare confirmation, verification or funds effects")

    def bank_facts():
        with sqlite3.connect(bank_path) as connection:
            return tuple(tuple(connection.execute(query)) for query in (
                "SELECT * FROM accounts ORDER BY account_id",
                "SELECT * FROM bank_operations ORDER BY operation_id",
                "SELECT * FROM ledger_entries ORDER BY transaction_id"))

    with_gateway = BankGateway(bank)
    try:
        def read_handler(current, payload):
            calls.append(payload["account_id"])
            # Identity remains server-owned; the requested account is untrusted.
            return with_gateway.list_transactions(trusted, payload["account_id"],
                datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 10, 1, tzinfo=timezone.utc))

        registry = ToolRegistry()
        declaration = BILLS_PRIVATE_TOOLS[1]
        registry.register(declaration, read_handler)
        gate = SecurityGate(registry, ConfirmationService(tmp_path / "security.sqlite"),
            scope_authorizer=policy.authorize_tool, task_state_resolver=lambda *_: stopped[0],
            risk_assessor=policy.assess_risk, confirmation_preparer=no_sensitive_flow,
            verification_preparer=no_sensitive_flow, verification_resolver=no_sensitive_flow,
            challenge_resolver=no_sensitive_flow, decision_sink=decisions.append,
            snapshot_writer=no_sensitive_flow, summary_validator=lambda *_: False)
        executor = DeterministicExecutor(gate, parameter_resolver=lambda *_: dict(parameters),
            operation_lookup=no_sensitive_flow, result_observer=no_sensitive_flow)
        action = action_for(declaration.name).model_copy(update={"phase": Phase.ADMISSION})
        before = bank_facts()
        own = executor.execute(context, action)
        assert own.executed and isinstance(own.result, QueryOk)
        assert own.result.data.transactions
        assert {row.account_id for row in own.result.data.transactions} == {"A1"}
        errors = []
        for account in ("U2A1", "missing-account"):
            parameters["account_id"] = account
            outcome = executor.execute(context, action)
            assert isinstance(outcome.result, QueryFailure)
            errors.append(outcome.result.model_dump(mode="json"))
        assert errors[0] == errors[1]
        assert errors[0]["error"]["code"] == "ACCESS_DENIED"
        count = len(calls)
        for denied_context in (context.model_copy(update={"user_id": "U2"}),
                               context.model_copy(update={"demo_round_id": "old-round"})):
            outcome = executor.execute(denied_context, action)
            assert not outcome.executed and outcome.decision.decision == "block"
        stopped[0] = True
        assert not executor.execute(context, action).executed
        assert len(calls) == count
        assert decisions and any(d.decision == "allow" for d in decisions)
        assert all("bills-own-account-read" in d.rule_ids for d in decisions if d.decision == "allow")
        assert bank_facts() == before
    finally:
        with_gateway.close()
