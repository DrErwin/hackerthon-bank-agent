"""Issue #177: L03 bills.generate_report joins the security-owned allowlist.

These offline checks prove the frozen declaration, the exact-match authorization
and the fail-closed boundaries only. They do not certify report content and are
not a human security sign-off.
"""
import pytest

from app.contracts.common import OperationLevel
from app.contracts.platform import TrustedContext
from app.modules.bills.manifest import MANIFEST as BILLS_MANIFEST
from app.modules.bills.manifest import REPORT_MANIFEST
from app.security.test_demo_policy import ROUND, USER, make_policy


DECLARATION = REPORT_MANIFEST.capabilities[0]


def unavailable_facts(*args):
    raise AssertionError("L03 capability checks must not need transfer risk facts")


def trusted(**changes):
    context = TrustedContext(
        user_id=USER,
        session_id="session-1",
        task_id="task-1",
        run_id="run-1",
        parent_task_id=None,
        demo_round_id=ROUND,
    )
    return context.model_copy(update=changes)


def test_l03_declaration_is_whitelisted_for_the_demo_scope():
    policy, _ = make_policy(unavailable_facts)

    # The authorization itself is the regression this issue fixes: it is False
    # before the frozen L03 snapshot is added to the allowlist.
    assert DECLARATION.name == "bills.generate_report"
    assert policy.authorize_capability(trusted(), DECLARATION)
    # L01 and its private reads stay authorized; this change only adds L03.
    assert policy.authorize_capability(trusted(), BILLS_MANIFEST.capabilities[0])
    # The authorized set changed, so decisions must carry the bumped version.
    assert policy.policy_version == "v04-main-declarations-l02-sensitive-5"


@pytest.mark.parametrize("change", [
    {"required_permissions": []},
    {"operation_level": OperationLevel.MODIFY},
    {"side_effect": True},
    {"confirmation_policy": "per_action"},
    {"timeout_ms": 9999},
    {"retry_policy": "none"},
    {"handler_ref": "bills.other_handler"},
    {"input_schema_ref": "OtherInput"},
    {"output_schema_ref": "OtherOutput"},
])
def test_every_l03_declaration_field_is_pinned(change):
    policy, _ = make_policy(unavailable_facts)

    assert not policy.authorize_capability(trusted(), DECLARATION.model_copy(update=change))


def test_module_mutation_cannot_mutate_the_security_allowlist(monkeypatch):
    policy, _ = make_policy(unavailable_facts)
    policy_reviewed = DECLARATION.model_copy()
    monkeypatch.setattr(DECLARATION, "timeout_ms", DECLARATION.timeout_ms + 1)

    # The drifted module object is refused, while the declaration the security
    # owner reviewed still passes: the policy keeps its own frozen copy and a
    # module release (or an in-place mutation) cannot silently widen the allowlist.
    assert not policy.authorize_capability(trusted(), DECLARATION)
    assert policy.authorize_capability(trusted(), policy_reviewed)


@pytest.mark.parametrize("name", [
    "bills.unknown", "bills.export_details", "bills.bank.list_accounts",
])
def test_unknown_capabilities_remain_default_denied(name):
    policy, _ = make_policy(unavailable_facts)

    assert not policy.authorize_capability(
        trusted(), DECLARATION.model_copy(update={"name": name}),
    )


@pytest.mark.parametrize("changes", [{"user_id": "other-user"}, {"demo_round_id": "old-round"}])
def test_l03_whitelist_does_not_bypass_user_or_round_scope(changes):
    policy, _ = make_policy(unavailable_facts)

    assert not policy.authorize_capability(trusted(**changes), DECLARATION)


def test_l03_whitelist_requires_the_server_current_round():
    policy, current_round = make_policy(unavailable_facts)
    current_round[0] = "next-round"

    assert not policy.authorize_capability(trusted(), DECLARATION)

