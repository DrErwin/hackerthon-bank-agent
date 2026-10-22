"""Read-only public discovery keeps the security-owned declaration boundary."""

import pytest

from app.contracts.common import OperationLevel
from app.contracts.platform import CapabilityDefinition, TrustedContext
from .test_demo_policy import make_policy, evidence, USER, ROUND


def declaration(name):
    return CapabilityDefinition(name="transfer." + name, input_schema_ref="StartTransferInput",
        output_schema_ref="ModuleResult[AccountList]" if name == "list_accounts" else "ModuleResult[PayeeList]",
        required_permissions=["transfer.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=4_000,
        retry_policy="read_only", handler_ref="agent_platform.own_bank_queries." + name)


def context(**changes):
    return TrustedContext(user_id=USER, session_id="S1", demo_round_id=ROUND,
                          task_id="T1", run_id="R1", parent_task_id=None).model_copy(update=changes)


@pytest.mark.parametrize("name", ["list_accounts", "list_payees"])
def test_own_query_and_scope_boundary(name):
    policy, _ = make_policy(lambda *_: evidence())
    item = declaration(name)
    assert policy.authorize_capability(context(), item)
    assert not policy.authorize_capability(context(user_id="OTHER"), item)
    assert not policy.authorize_capability(context(demo_round_id="OLD"), item)


@pytest.mark.parametrize("name", ["list_accounts", "list_payees"])
@pytest.mark.parametrize("changes", [
    {"side_effect": True}, {"operation_level": OperationLevel.SENSITIVE},
    {"required_permissions": ["transfer.submit"]}, {"confirmation_policy": "per_action"},
    {"input_schema_ref": "Other"}, {"output_schema_ref": "Other"},
    {"retry_policy": "none"}, {"timeout_ms": 5000}, {"handler_ref": "other"},
    {"name": "transfer.read_other_user"},
])
def test_any_declaration_drift_is_denied(name, changes):
    policy, _ = make_policy(lambda *_: evidence())
    assert not policy.authorize_capability(context(), declaration(name).model_copy(update=changes))
