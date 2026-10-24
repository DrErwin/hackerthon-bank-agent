"""The cross module's public capability declaration (contract §5.4)."""

from app.contracts.common import OperationLevel
from app.contracts.platform import CapabilityDefinition, ModuleManifest


CROSS_MANIFEST = ModuleManifest(
    module_name="cross", version="0.5.0-cross-1", owner="Erwin",
    description=(
        "生活目标编排：减支（账单对比/签约盘点→逐项受控退订→总回执）；"
        "养老金（资金范围/留存采用→D1→逐笔转账）；生日（真实商品→预算采用→冻结→"
        "下单→按订单核销→限定释放，写动作走生日安全门）"
    ),
    implementation_kind="workflow", dependencies=["bank_gateway", "security_gate"],
    capabilities=[CapabilityDefinition(
        name="cross.start_task", input_schema_ref="CrossStartInput",
        output_schema_ref="ModuleResult[CrossTaskView]",
        required_permissions=["cross.start"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=60_000,
        retry_policy="none", handler_ref="cross.entry.start",
    )],
)
