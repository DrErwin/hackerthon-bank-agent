"""Runnable L01 surface; L02 and L03 use independent manifests and factories.

Per Erwin's 2026-10-14 priority note, the platform may start integration from
bills.summarize. Register before ApiService construction: the old three-method
stub then steps aside as a whole. This module never edits the platform registry
or keeps a misleading successful stub for unimplemented methods.
"""
from app.contracts.common import OperationLevel
from app.contracts.platform import CapabilityDefinition, ModuleManifest
from .reads import PRIVATE_TOOLS

MANIFEST = ModuleManifest(
    module_name="bills", version="0.4.0-l01", owner="zhouey314-cloud",
    description="L01按mode返回：summary=SpendingSummary、details=BillDetails。",
    implementation_kind="workflow", dependencies=["bank_gateway", "security"],
    capabilities=[CapabilityDefinition(
        # A schema_ref must name an existing model, not an invented union alias.
        # The manifest description explicitly declares the details-mode type.
        name="bills.summarize", input_schema_ref="BillSummarizeInput",
        output_schema_ref="SpendingSummary",
        required_permissions=["bills.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=10_000,
        retry_policy="read_only", handler_ref="bills.summarize",
    )],
)


# L03 uses a separate factory/entry from L01: a ModuleManifest shares its
# factory across every declared capability, so blindly appending L03 to
# MANIFEST would route report intent to the summary handler.
REPORT_MANIFEST = ModuleManifest(
    module_name="bills", version="0.4.0-l03", owner="zhouey314-cloud",
    description="月度或年度本人账单报告（L03）：只含总览、分类、对比；分享意图不授予分享权限。",
    implementation_kind="workflow", dependencies=["bank_gateway", "security"],
    capabilities=[CapabilityDefinition(
        name="bills.generate_report", input_schema_ref="GenerateReportInput",
        output_schema_ref="BillReport", required_permissions=["bills.read"],
        operation_level=OperationLevel.READ, side_effect=False,
        confirmation_policy="none", timeout_ms=10_000, retry_policy="read_only",
        handler_ref="bills.generate_report",
    )],
)
