"""Issue164: mutable business declarations must not mutate security expectations."""

from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.contracts.common import OperationLevel, Phase, SecurityDecisionCode
from app.contracts.security import ActionDescriptor
from app.modules.subscription.manifest import MANIFEST
from app.modules.subscription.reads import PRIVATE_TOOLS
from app.modules.transfer.manifest import MANIFEST as TRANSFER_MANIFEST
from app.modules.transfer.manifest import PRIVATE_TOOLS as TRANSFER_PRIVATE_TOOLS
from app.security import DeterministicExecutor
from app.security import test_subscription_policy as helpers


PUBLIC_DECLARATIONS = (*MANIFEST.capabilities, *TRANSFER_MANIFEST.capabilities)
DECLARATIONS = (*PUBLIC_DECLARATIONS, *PRIVATE_TOOLS, *TRANSFER_PRIVATE_TOOLS)
FIELDS = ("name", "input_schema_ref", "output_schema_ref", "required_permissions",
          "operation_level", "side_effect", "confirmation_policy", "timeout_ms",
          "retry_policy", "handler_ref")


def action(declaration):
    return ActionDescriptor(action_name=declaration.name, parameters_ref="P1", resource_refs=[],
                            phase=Phase.EXECUTION)


def authorized(policy, declaration):
    if declaration in PUBLIC_DECLARATIONS:
        return policy.authorize_capability(helpers.trusted(), declaration)
    return policy.authorize_tool(helpers.security_context(), action(declaration), declaration)


@pytest.mark.parametrize("declaration", DECLARATIONS, ids=lambda item: item.name)
def test_original_module_declarations_remain_authorized(declaration):
    assert authorized(helpers.policy_for(helpers.LOW_SIGNALS), declaration)


@pytest.mark.parametrize("declaration", DECLARATIONS, ids=lambda item: item.name)
@pytest.mark.parametrize("field", FIELDS)
def test_every_in_place_declaration_change_requires_new_security_review(declaration, field):
    policy = helpers.policy_for(helpers.LOW_SIGNALS)
    current = getattr(declaration, field)
    if field == "required_permissions":
        changed = ["subscription.read"] if current == ["subscription.cancel"] else ["subscription.cancel"]
    elif field == "operation_level":
        changed = OperationLevel.READ if current != OperationLevel.READ else OperationLevel.MODIFY
    elif field == "side_effect":
        changed = not current
    elif field == "confirmation_policy":
        changed = "none" if current != "none" else "per_action"
    elif field == "retry_policy":
        changed = "none" if current != "none" else "read_only"
    elif field == "timeout_ms":
        changed = current + 1
    else:
        changed = current + ".changed"
    with raw_field_drift(declaration, field, changed):
        assert not authorized(policy, declaration)


@contextmanager
def raw_field_drift(declaration, field, changed):
    # Exercise the policy boundary even when typed assignment would reject an
    # inconsistent combination before it reaches the gate. The object is restored.
    original = getattr(declaration, field)
    object.__setattr__(declaration, field, changed)
    try:
        yield
    finally:
        object.__setattr__(declaration, field, original)


@pytest.mark.parametrize("declaration", DECLARATIONS, ids=lambda item: item.name)
def test_nested_permission_list_change_is_rejected(declaration):
    policy = helpers.policy_for(helpers.LOW_SIGNALS)
    original = list(declaration.required_permissions)
    try:
        declaration.required_permissions.clear()
        assert not authorized(policy, declaration)
    finally:
        declaration.required_permissions[:] = original


@pytest.mark.parametrize("declaration", [helpers.CANCEL, TRANSFER_PRIVATE_TOOLS[-1]],
                         ids=lambda item: item.name)
def test_in_place_write_downgrade_stops_before_handler(tmp_path, monkeypatch, declaration):
    policy = helpers.policy_for(helpers.LOW_SIGNALS)
    gate, _, _, _ = helpers.build_gate(tmp_path, policy, declaration)
    calls = []
    registered = gate.registry.get(declaration.name)
    # Keep the actual registered declaration and use a harmless handler spy.
    monkeypatch.setitem(gate.registry._tools, declaration.name,
                        replace(registered, handler=lambda *_: calls.append(True)))
    executor = DeterministicExecutor(gate, parameter_resolver=lambda *_: {},
                                     operation_lookup=lambda *_: None, result_observer=lambda *_: None)
    context = helpers.security_context(operation_id=None, action_revision=None)
    read_permission = "transfer.read" if declaration.name.startswith("bank.") else "subscription.read"
    with patch.object(declaration, "required_permissions", [read_permission]), \
            patch.object(declaration, "operation_level", OperationLevel.READ), \
            patch.object(declaration, "side_effect", False), \
            patch.object(declaration, "confirmation_policy", "none"):
        outcome = executor.execute(context, action(declaration))
        assert not outcome.executed
        assert outcome.decision.decision == SecurityDecisionCode.BLOCK
        assert calls == []

