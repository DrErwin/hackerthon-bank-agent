"""Frozen birthday tool declarations, risk rules, and the §3.5 clause.

Security owns this frozen snapshot exactly like the transfer/subscription
declarations in demo_policy: a business release must not silently change the
set of authorized birthday tools. The money writes (freeze, order, capture)
are SENSITIVE side effects under per_action confirmation and MEDIUM risk, so
each purchase carries its own step-up verification (contract §4); reads of the
user's own freeze/order/product facts are LOW.

bank.release_frozen is deliberately NOT declared here: the model must not
initiate the ending release. It exists only on the controlled finalization
path in birthday_release, and the ordinary executor refuses it as an
unregistered tool.
"""

from __future__ import annotations

from collections.abc import Callable

from app.contracts.common import DisplayField, OperationLevel, RiskLevel
from app.contracts.platform import CapabilityDefinition
from app.contracts.security import ActionDescriptor, ExecutionSecurityContext
from app.security.gate import RiskAssessment, RiskFactsUnavailable


FREEZE_RELEASE_CLAUSE = (
    "这次安排结束时（办完、您取消或因安全原因停止），没花完的钱会退回原卡；"
    "结束后不会再下单或付款，已经付掉的钱不退。"
)
RELEASE_CLAUSE_FIELD = "release_clause"


def with_release_clause(fields: list[DisplayField]) -> list[DisplayField]:
    """Append the §3.5 clause a freeze confirmation must display."""
    if any(field.name == RELEASE_CLAUSE_FIELD for field in fields):
        raise ValueError("release clause already present")
    return [*fields, DisplayField(
        name=RELEASE_CLAUSE_FIELD, label="没花完的钱怎么办", value_text=FREEZE_RELEASE_CLAUSE,
    )]


def has_release_clause(fields: list[DisplayField]) -> bool:
    return any(
        field.name == RELEASE_CLAUSE_FIELD and field.value_text == FREEZE_RELEASE_CLAUSE
        for field in fields
    )


BIRTHDAY_TOOLS = (
    CapabilityDefinition(
        name="bank.freeze_funds", input_schema_ref="FreezeFundsInput",
        output_schema_ref="OperationResult[FreezeReceipt]",
        required_permissions=["cross.birthday.submit"],
        operation_level=OperationLevel.SENSITIVE, side_effect=True,
        confirmation_policy="per_action", timeout_ms=4_000, retry_policy="none",
        handler_ref="bank_gateway.freeze_funds",
    ),
    CapabilityDefinition(
        name="bank.create_order", input_schema_ref="CreateOrderInput",
        output_schema_ref="OperationResult[OrderResult]",
        required_permissions=["cross.birthday.submit"],
        operation_level=OperationLevel.SENSITIVE, side_effect=True,
        confirmation_policy="per_action", timeout_ms=4_000, retry_policy="none",
        handler_ref="bank_gateway.create_order",
    ),
    CapabilityDefinition(
        name="bank.capture_frozen", input_schema_ref="CaptureFrozenInput",
        output_schema_ref="OperationResult[CaptureReceipt]",
        required_permissions=["cross.birthday.submit"],
        operation_level=OperationLevel.SENSITIVE, side_effect=True,
        confirmation_policy="per_action", timeout_ms=4_000, retry_policy="none",
        handler_ref="bank_gateway.capture_frozen",
    ),
    *(CapabilityDefinition(
        name="bank." + name, input_schema_ref=input_ref,
        output_schema_ref=output_ref, required_permissions=["cross.birthday.read"],
        operation_level=OperationLevel.READ, side_effect=False,
        confirmation_policy="none", timeout_ms=4_000, retry_policy="read_only",
        handler_ref="bank_gateway." + name,
    ) for name, input_ref, output_ref in (
        ("get_freeze", "GetFreezeInput", "QueryResult[FreezeView]"),
        ("get_order", "GetOrderInput", "QueryResult[OrderResult]"),
        ("list_products", "ListProductsInput", "ProductList"),
    )),
)

BIRTHDAY_WRITE_NAMES = frozenset(
    item.name for item in BIRTHDAY_TOOLS if item.side_effect
)


class BirthdaySecurityPolicy:
    """Scope and risk callbacks for the birthday scenario's frozen tool set."""

    policy_version = "v05-birthday-security-policy-1"
    _permissions = frozenset({"cross.birthday.read", "cross.birthday.submit"})
    _tools = {item.name: item for item in BIRTHDAY_TOOLS}

    def __init__(self, *, demo_user_id: str, current_demo_round: Callable[[], str]):
        if not demo_user_id.strip():
            raise ValueError("demo identity must be configured")
        self.demo_user_id = demo_user_id
        self.current_demo_round = current_demo_round

    def _in_current_scope(self, user_id: str, demo_round_id: str) -> bool:
        try:
            current_round = self.current_demo_round()
        except Exception:
            return False
        return (
            isinstance(current_round, str)
            and bool(current_round)
            and user_id == self.demo_user_id
            and demo_round_id == current_round
        )

    def authorize_tool(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        declaration: CapabilityDefinition,
    ) -> bool:
        expected = self._tools.get(declaration.name)
        return (
            isinstance(context, ExecutionSecurityContext)
            and isinstance(action, ActionDescriptor)
            and self._in_current_scope(context.user_id, context.demo_round_id)
            and action.action_name == declaration.name
            and expected is not None
            and declaration == expected
            and set(declaration.required_permissions) <= self._permissions
        )

    def assess_risk(
        self,
        context: ExecutionSecurityContext,
        action: ActionDescriptor,
        declaration: CapabilityDefinition,
    ) -> RiskAssessment:
        if not self.authorize_tool(context, action, declaration):
            raise RiskFactsUnavailable(
                "action is outside the authorized birthday scope",
                rule_id="birthday-risk-out-of-scope",
                policy_version=self.policy_version,
            )
        if declaration.name in BIRTHDAY_WRITE_NAMES:
            # Every money commitment is a fresh MEDIUM action: its own
            # confirmation plus step-up verification; a parent plan's approval
            # never substitutes for the item (contract §4, spec table).
            return RiskAssessment(
                RiskLevel.MEDIUM, self.policy_version,
                "birthday-money-write-step-up",
                "contract:公共契约§3.5+§4",
            )
        return RiskAssessment(
            RiskLevel.LOW, self.policy_version,
            "birthday-own-fact-read",
            "contract:安全附件§2",
        )
