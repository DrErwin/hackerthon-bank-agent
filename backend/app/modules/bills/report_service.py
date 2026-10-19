"""L03 typed report preparation over already-authorized L01 statistics.

Produces a BillReport value ONLY. The platform must still authorize and persist
it for F21/F22/F24; this module never issues a download grant or shares data.
"""
from __future__ import annotations

from datetime import datetime, time
from uuid import uuid4

from pydantic import ValidationError

from app.contracts.bills import GenerateReportInput, SpendingSummary
from app.contracts.common import TaskStatus
from app.contracts.platform import TrustedContext
from app.contracts.tasks import ModuleResult
from ._statistics import BEIJING
from ._report import report_from_verified_summary
from .service import BillsError, BillsService, fail


def covered_days(scope, as_of: datetime, now: datetime) -> int:
    """Number of Beijing natural dates in the available half-open interval."""
    start = scope.start_at.astimezone(BEIJING)
    end = min(scope.end_at, as_of, now).astimezone(BEIJING)
    if end <= start:
        return 0
    days = (end.date() - start.date()).days
    if end.time() != time.min:
        days += 1
    return max(0, days)


class BillsReportService(BillsService):
    def generate_report(self, trusted: TrustedContext,
                        request: GenerateReportInput | dict) -> ModuleResult:
        try:
            # Validate public contract before any bank read. "share_request"
            # is only a purpose label, never a disclosure permission.
            validated = GenerateReportInput.model_validate(
                request.model_dump(mode="python") if isinstance(request, GenerateReportInput) else request
            )
        except (ValidationError, ValueError, TypeError):
            return fail(trusted, BillsError("INVALID_ARGUMENT"))

        raw = self.summarize(trusted, {
            "scope": validated.scope.model_dump(mode="python"), "mode": "summary",
            "comparison_scope": validated.comparison_scope.model_dump(mode="python")
                                if validated.comparison_scope else None,
        })
        if raw.status != TaskStatus.SUCCEEDED:
            return raw
        if not isinstance(raw.data, SpendingSummary):
            return fail(trusted, BillsError("INCOMPLETE_FACTS"))
        try:
            completed_at = self.clock()
            if completed_at.tzinfo is None:
                raise ValueError("naive_clock")
            days = covered_days(validated.scope, raw.data.as_of, completed_at)
            report = report_from_verified_summary(
                raw.data, report_id=str(uuid4()), statistical_days=days,
                generated_at=completed_at, purpose=validated.purpose,
            )
        except (ValidationError, ValueError, TypeError):
            return fail(trusted, BillsError("INCOMPLETE_FACTS"))
        return ModuleResult(task_id=trusted.task_id, run_id=trusted.run_id,
            status=TaskStatus.SUCCEEDED, data=report,
            message=report.spoken_summary, interaction=None, error=None,
            allowed_actions=[], recovery_required=False, recovery_reason=None)
