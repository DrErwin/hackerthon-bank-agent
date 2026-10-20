"""L03 is an own-account read, never a sensitive export or sharing grant."""

import pytest

from app.contracts.common import OperationLevel
from app.modules.bills.manifest import REPORT_MANIFEST
from app.security.test_demo_policy import make_policy
from app.contracts.platform import TrustedContext


def trusted(**overrides):
    values = dict(user_id="demo-user-1", session_id="S1", demo_round_id="demo-round-1",
                  task_id="T1", run_id="R1", parent_task_id=None)
    return TrustedContext(**{**values, **overrides})


def test_report_capability_matches_the_independent_security_snapshot():
    policy, _ = make_policy(lambda *_: None)
    assert policy.authorize_capability(trusted(), REPORT_MANIFEST.capabilities[0])


@pytest.mark.parametrize("change", [
    {"required_permissions": []}, {"required_permissions": ["transfer.submit"]},
    {"operation_level": OperationLevel.MODIFY}, {"side_effect": True},
    {"confirmation_policy": "per_action"}, {"timeout_ms": 9999},
    {"retry_policy": "none"}, {"handler_ref": "bills.other"},
    {"input_schema_ref": "OtherInput"}, {"output_schema_ref": "OtherOutput"},
])
def test_report_declaration_drift_stays_denied(change):
    policy, _ = make_policy(lambda *_: None)
    assert not policy.authorize_capability(
        trusted(), REPORT_MANIFEST.capabilities[0].model_copy(update=change))


def test_module_mutation_does_not_mutate_security_expectations(monkeypatch):
    policy, _ = make_policy(lambda *_: None)
    declaration = REPORT_MANIFEST.capabilities[0]
    monkeypatch.setattr(declaration, "timeout_ms", 1)
    assert not policy.authorize_capability(trusted(), declaration)


@pytest.mark.parametrize("scope", [{"user_id": "other-user"},
                                    {"demo_round_id": "old-round"}])
def test_report_scope_is_server_owned(scope):
    policy, _ = make_policy(lambda *_: None)
    assert not policy.authorize_capability(trusted(**scope), REPORT_MANIFEST.capabilities[0])


@pytest.mark.parametrize("name", ["bills.export_details", "bills.share_report", "bills.bank.submit_transfer"])
def test_report_read_permission_does_not_authorize_other_capabilities(name):
    policy, _ = make_policy(lambda *_: None)
    declaration = REPORT_MANIFEST.capabilities[0].model_copy(update={"name": name})
    assert not policy.authorize_capability(trusted(), declaration)


def test_real_report_uses_public_and_each_private_policy_check_without_money_effects(tmp_path):
    import sqlite3
    from uuid import uuid4
    from app.agent_platform.model import TransferProposal
    from app.contracts.bills import BillReport
    from app.modules.bills.entry import register_bills_report
    from app.modules.bills.test_public_integration import Environment, BANK_NOW, trusted as bank_context
    from app.security.demo_policy import DemoSecurityPolicy

    policy = DemoSecurityPolicy(demo_user_id="U1", admin_actor_id="admin",
        current_demo_round=lambda: "D1", risk_facts=lambda *_: None)

    class PolicyEnvironment(Environment):
        def reads_factory(self, context, trace):
            reads = super().reads_factory(context, trace)
            reads.gate.scope_authorizer = lambda current, action, declaration: (
                self.valid_session(current) and policy.authorize_tool(current, action, declaration))
            reads.gate.risk_assessor = policy.assess_risk
            return reads

    class ReportPlanner:
        provider = "scripted"
        model_name = "security-L03-offline"
        config_version = "test-l03-policy-1"
        def select(self, *args, **kwargs):
            return TransferProposal(capability_name="bills.generate_report")

    env = PolicyEnvironment(tmp_path)
    try:
        register_bills_report(env.registry, env.reads_factory, lambda: BANK_NOW)
        env.harness.authorize_capability = lambda current, declaration: (
            env.valid_session(current) and policy.authorize_capability(current, declaration))
        env.harness.planner = ReportPlanner()
        def bank_facts():
            with sqlite3.connect(tmp_path / "bank.sqlite") as connection:
                return tuple(tuple(connection.execute(query)) for query in (
                    "SELECT * FROM accounts ORDER BY account_id",
                    "SELECT * FROM bank_operations ORDER BY operation_id",
                    "SELECT * FROM ledger_entries ORDER BY transaction_id"))
        before = bank_facts()
        result = env.harness.start(bank_context(), uuid4(), "2026年9月所有账户账单报告")
        assert result.status == "succeeded"
        assert isinstance(result.data, BillReport)
        assert env.decisions and all(decision.decision == "allow" for decision in env.decisions)
        assert all("bills-own-account-read" in decision.rule_ids for decision in env.decisions)
        assert env.gateway.bank_writes == 0 and bank_facts() == before
        assert result.allowed_actions == []
    finally:
        env.close()
