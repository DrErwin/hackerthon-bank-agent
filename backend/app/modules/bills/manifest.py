"""Runnable L01 surface; absent L02/L03 are not advertised as completed.

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
    description="本人账单查询、分类统计与明细（L01）；异常识别L02和报告L03尚未实现，不能宣称已完成。",
    implementation_kind="workflow", dependencies=["bank_gateway", "security"],
    capabilities=[CapabilityDefinition(
        # BillSummarizeInput.mode controls the frozen union; summary and details
        # are both truthful public outputs (no new common contract model).
        name="bills.summarize", input_schema_ref="BillSummarizeInput",
        output_schema_ref="SpendingSummary|BillDetails",
        required_permissions=["bills.read"], operation_level=OperationLevel.READ,
        side_effect=False, confirmation_policy="none", timeout_ms=10_000,
        retry_policy="read_only", handler_ref="bills.summarize",
    )],
)
