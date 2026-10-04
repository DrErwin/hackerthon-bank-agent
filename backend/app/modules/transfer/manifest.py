"""The v0.3 ordinary-transfer capability and its controlled private tools."""

from app.contracts.common import OperationLevel
from app.contracts.platform import CapabilityDefinition, ModuleManifest


PRIVATE_TOOLS = (
    CapabilityDefinition(
        name=name,
        input_schema_ref=input_schema,
        output_schema_ref=output_schema,
        required_permissions=["transfer.read"],
        operation_level=OperationLevel.READ,
        side_effect=False,
        confirmation_policy="none",
        timeout_ms=4_000,
        retry_policy="read_only",
        handler_ref=f"bank_gateway.{name.removeprefix('bank.')}",
    )
    for name, input_schema, output_schema in (
        ("bank.list_accounts", "TrustedContext", "AccountList"),
        ("bank.list_payees", "PayeeSearch", "PayeeList"),
        ("bank.verify_payee", "PayeeInput", "PayeeVerification"),
        ("bank.precheck_transfer", "TransferDraft", "TransferPrecheck"),
    )
)

PRIVATE_TOOLS = tuple(PRIVATE_TOOLS) + (
    CapabilityDefinition(
        name="bank.submit_transfer",
        input_schema_ref="TransferDraft",
        output_schema_ref="OperationResult[TransferReceipt]",
        required_permissions=["transfer.submit"],
        operation_level=OperationLevel.SENSITIVE,
        side_effect=True,
        confirmation_policy="per_action",
        timeout_ms=4_000,
        retry_policy="none",
        handler_ref="bank_gateway.submit_transfer",
    ),
)

MANIFEST = ModuleManifest(
    module_name="transfer",
    version="0.3.0",
    owner="LiangShuang",
    description="普通转账、受控收款资料及同任务恢复；v0.3 由 Erwin 临时实现",
    implementation_kind="workflow",
    capabilities=[
        CapabilityDefinition(
            name="transfer.start_transfer",
            input_schema_ref="StartTransferInput",
            output_schema_ref="ModuleResult[TransferTaskView]",
            required_permissions=["transfer.start"],
            operation_level=OperationLevel.MODIFY,
            side_effect=False,
            confirmation_policy="none",
            timeout_ms=30_000,
            retry_policy="none",
            handler_ref="transfer.workflow.start",
        ),
    ],
    dependencies=["bank_gateway", "security_gate"],
)
