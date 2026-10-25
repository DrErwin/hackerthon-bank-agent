"""Independent L02 declaration for the platform's per-capability entry factory."""
from app.contracts.common import OperationLevel
from app.contracts.platform import CapabilityDefinition, ModuleManifest


ANOMALY_MANIFEST = ModuleManifest(
    module_name="bills", version="0.4.0-l02", owner="zhouey314-cloud",
    description=("接收聊天或DetectAnomaliesInput。locate 返回 TransactionCandidates，聊天多候选时等待选择；"
                 "single 返回含银行原交易的 AnomalyResult；scan 只检查周期扣款规则4。"),
    implementation_kind="workflow", dependencies=["bank_gateway", "security"],
    capabilities=[CapabilityDefinition(
        name="bills.detect_anomalies", input_schema_ref="DetectAnomaliesInput",
        output_schema_ref="AnomalyResult", required_permissions=["bills.read"],
        operation_level=OperationLevel.READ, side_effect=False,
        confirmation_policy="none", timeout_ms=10_000, retry_policy="read_only",
        handler_ref="bills.detect_anomalies",
    )],
)
