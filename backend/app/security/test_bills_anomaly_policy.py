"""Issue #187: L02 independent admission and real read-only gate regression.

Harness uses a scripted planner and explicit module registration. This does not
prove production local_demo registration, HTTP, model or frontend acceptance.
"""
from datetime import timedelta
import sqlite3
from uuid import uuid4

import pytest

from app.agent_platform.harness import AgentHarness
from app.contracts.common import OperationLevel, TaskStatus
from app.modules.bills.anomaly_entry import register_bills_anomalies
from app.modules.bills.anomaly_manifest import ANOMALY_MANIFEST
from app.modules.bills.manifest import MANIFEST, REPORT_MANIFEST
from app.modules.bills.reads import GatewayBillsReads
from app.modules.bills.test_anomaly_integration import AnomalyPlanner, f10
from app.modules.bills.test_public_integration import BANK_NOW, Environment, trusted
from app.security import ConfirmationService, SecurityGate, ToolRegistry
from app.security.demo_policy import DemoSecurityPolicy
from app.security.test_bills_report_policy import trusted as policy_context, unavailable_facts
from app.security.test_demo_policy import make_policy


DECLARATION = ANOMALY_MANIFEST.capabilities[0]


def test_l02_admission_preserves_l01_and_l03_without_new_permissions():
    policy, _ = make_policy(unavailable_facts)
    for declaration in (MANIFEST.capabilities[0], REPORT_MANIFEST.capabilities[0], DECLARATION):
        assert policy.authorize_capability(policy_context(), declaration)
    assert policy.policy_version == "v04-local-demo-read-4"


@pytest.mark.parametrize("change", [
    {"name": "bills.unknown"}, {"required_permissions": []},
    {"required_permissions": ["transfer.read"]}, {"operation_level": OperationLevel.MODIFY},
    {"side_effect": True}, {"confirmation_policy": "per_action"}, {"timeout_ms": 9999},
    {"retry_policy": "none"}, {"handler_ref": "bills.other_handler"},
    {"input_schema_ref": "OtherInput"}, {"output_schema_ref": "OtherOutput"},
])
def test_l02_pins_every_declaration_field(change):
    policy, _ = make_policy(unavailable_facts)
    assert not policy.authorize_capability(policy_context(), DECLARATION.model_copy(update=change))


@pytest.mark.parametrize("field,value", [("timeout_ms", 1), ("required_permissions", [])])
def test_l02_module_mutation_cannot_change_security_snapshot(monkeypatch, field, value):
    policy, _ = make_policy(unavailable_facts)
    reviewed = DECLARATION.model_copy(deep=True)
    monkeypatch.setattr(DECLARATION, field, value)
    assert not policy.authorize_capability(policy_context(), DECLARATION)
    assert policy.authorize_capability(policy_context(), reviewed)


@pytest.mark.parametrize("change", [{"user_id": "other-user"}, {"demo_round_id": "old-round"}])
def test_l02_rejects_scope_drift(change):
    policy, _ = make_policy(unavailable_facts)
    assert not policy.authorize_capability(policy_context(**change), DECLARATION)


def test_l02_requires_live_server_round():
    policy, current = make_policy(unavailable_facts)
    current[0] = "next-round"
    assert not policy.authorize_capability(policy_context(), DECLARATION)


@pytest.mark.parametrize("name", ["bills.export_details", "bills.bank.list_accounts", "bills.execute_refund"])
def test_l02_does_not_admit_unknown_or_private_capabilities(name):
    policy, _ = make_policy(unavailable_facts)
    assert not policy.authorize_capability(policy_context(), DECLARATION.model_copy(update={"name": name}))


class PolicyEnvironment(Environment):
    """Use the real demo policy at public admission and each private read."""

    def __init__(self, directory):
        super().__init__(directory)
        self.round = "D1"
        self.now = BANK_NOW
        self.policy = DemoSecurityPolicy(demo_user_id="U1", admin_actor_id="ADMIN1",
            current_demo_round=lambda: self.round, risk_facts=unavailable_facts)
        self.gateway._bank.clock = self.clock
        register_bills_anomalies(self.registry, self.reads_factory, self.clock)
        self.harness = AgentHarness(self.application, self.memory, self.audit, self.registry,
            AnomalyPlanner(), lambda context, declaration:
                self.valid_session(context) and self.policy.authorize_capability(context, declaration))

    def clock(self):
        self.now += timedelta(microseconds=1)
        return self.now

    def reads_factory(self, context, trace):
        def no_sensitive_flow(*args):
            raise AssertionError("L02 read cannot create confirmation, verification or money effects")

        def terminated(current):
            task = self.application.get_task(current.user_id, current.demo_round_id, current.task_id)
            if task is None or task.session_id != current.session_id:
                raise PermissionError("ACCESS_DENIED")
            return task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}

        gate = SecurityGate(ToolRegistry(), ConfirmationService(self.directory / "security.sqlite"),
            scope_authorizer=lambda current, action, declaration:
                self.valid_session(current) and self.policy.authorize_tool(current, action, declaration),
            task_state_resolver=terminated, risk_assessor=self.policy.assess_risk,
            confirmation_preparer=no_sensitive_flow, verification_preparer=no_sensitive_flow,
            verification_resolver=no_sensitive_flow, challenge_resolver=no_sensitive_flow,
            decision_sink=self.decisions.append, snapshot_writer=no_sensitive_flow,
            summary_validator=lambda *_: False)
        return GatewayBillsReads(self.gateway, gate, self.security_context, trace)

    def bank_facts(self):
        with sqlite3.connect(self.directory / "bank.sqlite") as connection:
            return tuple(tuple(connection.execute(query)) for query in (
                "SELECT * FROM accounts ORDER BY account_id",
                "SELECT * FROM bank_operations ORDER BY operation_id",
                "SELECT * FROM ledger_entries ORDER BY transaction_id"))


def test_real_policy_harness_candidate_resume_and_replay_keep_bank_unchanged(tmp_path):
    env = PolicyEnvironment(tmp_path)
    try:
        before = env.bank_facts()
        request_id = uuid4()
        first = env.harness.start(trusted(), request_id, "核对交易，2026年9月所有账户")
        assert first.status == "waiting_input"
        count = len(env.gateway.reads)
        replay = env.harness.start(trusted(), request_id, "核对交易，2026年9月所有账户")
        assert replay.interaction == first.interaction and len(env.gateway.reads) == count
        result = env.harness.resume(trusted(run="R2"), f10(first, 1))
        assert result.status == "succeeded" and result.task_id == "T1"
        assert env.decisions and all(d.decision == "allow" for d in env.decisions)
        assert all("bills-own-account-read" in d.rule_ids for d in env.decisions)
        assert all(env.policy.policy_version in d.policy_version for d in env.decisions)
        assert env.gateway.bank_writes == 0 and env.bank_facts() == before
    finally:
        env.close()


@pytest.mark.parametrize("isolate_private_gate", [False, True])
def test_real_admission_and_private_read_recheck_round_before_bank(tmp_path, isolate_private_gate):
    env = PolicyEnvironment(tmp_path)
    try:
        first = env.harness.start(trusted(), uuid4(), "核对交易，2026年9月所有账户")
        assert first.status == "waiting_input"
        before, count = env.bank_facts(), len(env.gateway.reads)
        env.round = "D2"
        if isolate_private_gate:
            # Deliberately bypass public admission in this variant only, to prove
            # the private read still checks the live real policy independently.
            env.harness.authorize_capability = lambda *_: True
            result = env.harness.resume(trusted(run="R2"), f10(first, 1))
            assert result.status == "failed" and result.error.source == "security"
            assert result.data is None
            assert any(d.decision == "block" for d in env.decisions)
        else:
            with pytest.raises(PermissionError, match="ACCESS_DENIED"):
                env.harness.resume(trusted(run="R2"), f10(first, 1))
        assert len(env.gateway.reads) == count
        assert env.bank_facts() == before and env.gateway.bank_writes == 0
    finally:
        env.close()

