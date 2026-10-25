"""The scenario-05 public capabilities; the bank tools stay private (contract §5.5)."""

from app.contracts.common import OperationLevel
from app.contracts.platform import CapabilityDefinition, ModuleManifest


MANIFEST = ModuleManifest(
    module_name="subscription",
    version="0.4.0",
    owner="Erwin",
    description=(
        "S01 代扣盘点与 30 天续费提醒（B29 签约 + B08 扣款证据 + 契约 §5.9 疑似线索）；"
        "S02 单笔本行签约代扣解约 / 明确停止未来扣费（确认门 + 会话级基础身份验证，逐笔、不可批量）"
    ),
    implementation_kind="workflow",
    capabilities=[
        CapabilityDefinition(
            name="subscription.list_subscriptions",
            input_schema_ref="SubscriptionListInput",
            output_schema_ref="ModuleResult[SubscriptionTaskView]",
            required_permissions=["subscription.read"],
            operation_level=OperationLevel.READ,
            side_effect=False,
            confirmation_policy="none",
            timeout_ms=30_000,
            retry_policy="read_only",
            handler_ref="subscription.list_subscriptions",
        ),
        CapabilityDefinition(
            name="subscription.cancel_subscription",
            input_schema_ref="SubscriptionCancelInput",
            output_schema_ref="ModuleResult[SubscriptionTaskView]",
            required_permissions=["subscription.cancel"],
            operation_level=OperationLevel.SENSITIVE,
            side_effect=True,
            confirmation_policy="per_action",
            timeout_ms=60_000,
            retry_policy="none",
            handler_ref="subscription.cancel_subscription",
        ),
    ],
    dependencies=["bank_gateway", "security_gate"],
)
