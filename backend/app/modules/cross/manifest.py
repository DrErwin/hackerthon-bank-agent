"""The cross module's public capability declaration (contract §5.4)."""

from app.contracts.common import OperationLevel
from app.contracts.platform import CapabilityDefinition, ModuleManifest


CROSS_MANIFEST = ModuleManifest(
    module_name="cross", version="0.5.0-cross-1", owner="Erwin",
    description=(
        "生活目标编排：减支（真实账单对比/签约盘点→用户选择→逐项受控退订→总回执）；"
        "养老金安排与生日编排由本组后续票接入"
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
