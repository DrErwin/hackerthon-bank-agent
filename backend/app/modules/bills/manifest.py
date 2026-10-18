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
    description="L01按mode返回：summary=SpendingSummary、details=BillDetails；L02/L03尚未实现。",
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
