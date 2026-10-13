"""Contract-shaped bills stub: registers L01—L03 until the bills module lands (v04-platform/03).

The stub proves the platform seam — registration, catalog, intent routing and the
task lifecycle — without copying the transfer runtime or reading bank data. The
real bills module (backend/app/modules/bills/, 周恩宇) replaces this factory by
registering the same capability names with real handlers; the L02 input/output
and L03 input schema refs follow contract §5.3 and resolve when the bills
contract models land.
"""

from __future__ import annotations

from app.contracts.common import OperationLevel, TaskStatus
from app.contracts.platform import (
    CapabilityDefinition, ModuleManifest, StartTransferInput, TrustedContext,
)
from app.contracts.tasks import ModuleResult

from .registry import TransferFactory

STUB_MESSAGE = "账单能力尚未接入真实业务模块，本次为契约形状桩响应，未读取账单数据。"

BILLS_MANIFEST = ModuleManifest(
    module_name="bills",
    version="0.4.0-stub",
    owner="Erwin",
    description="账单查询与分类统计、异常识别、月度/年度报告（桩：业务实现由账单模块提供）",
    implementation_kind="workflow",
    dependencies=["bank_gateway"],
    capabilities=[
        CapabilityDefinition(
            name="bills.summarize",
            input_schema_ref="BillSummarizeInput",
            output_schema_ref="SpendingSummary",
            required_permissions=["bills.read"],
            operation_level=OperationLevel.READ,
            side_effect=False,
            confirmation_policy="none",
            timeout_ms=10_000,
            retry_policy="read_only",
            handler_ref="bills.summarize",
        ),
        CapabilityDefinition(
            name="bills.detect_anomalies",
            input_schema_ref="DetectAnomaliesInput",
            output_schema_ref="AnomalyResult",
            required_permissions=["bills.read"],
            operation_level=OperationLevel.READ,
            side_effect=False,
            confirmation_policy="none",
            timeout_ms=10_000,
            retry_policy="read_only",
            handler_ref="bills.detect_anomalies",
        ),
        CapabilityDefinition(
            name="bills.generate_report",
            input_schema_ref="GenerateReportInput",
            output_schema_ref="BillReport",
            required_permissions=["bills.read"],
            operation_level=OperationLevel.READ,
            side_effect=False,
            confirmation_policy="none",
            timeout_ms=10_000,
            retry_policy="read_only",
            handler_ref="bills.generate_report",
        ),
    ],
)


class BillsStubEntry:
    """The TransferEntry protocol fulfilled by a no-op stub; no bank or model calls."""

    def __init__(self, trace):
        self._trace = trace

    def start(self, trusted: TrustedContext, request: StartTransferInput, *,
              thread_id: str | None = None) -> ModuleResult:
        return self._result(trusted)

    def resume(self, trusted: TrustedContext, response: dict, *,
               thread_id: str | None = None) -> ModuleResult:
        return self._result(trusted)

    def recover_session(self, trusted: TrustedContext, *, source_session_id: str,
                        thread_id: str | None = None) -> ModuleResult:
        return self._result(trusted)

    def checkpoint_context(self, trusted: TrustedContext, *,
                           thread_id: str | None = None) -> TrustedContext | None:
        return None

    def _result(self, trusted: TrustedContext) -> ModuleResult:
        return ModuleResult(
            task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.SUCCEEDED, data=None, message=STUB_MESSAGE,
            interaction=None, error=None, allowed_actions=[],
            recovery_required=False, recovery_reason=None,
        )


def bills_stub_factory(trusted: TrustedContext, saver, trace) -> BillsStubEntry:
    return BillsStubEntry(trace)


def register_bills_stub(registry) -> None:
    registry.register_module(BILLS_MANIFEST, bills_stub_factory)
