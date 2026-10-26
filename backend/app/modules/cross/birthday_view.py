"""Project receipt facts into the existing CrossStep fields, without bank rules."""

from app.contracts.common import TaskStatus
from app.contracts.cross import CrossStep


def _item_key(item: dict) -> str:
    """A plan row's execution identity (ticket 08), independent of the product."""
    return item.get("item_id") or item["product_id"]


def build_birthday_steps(birthday: dict) -> list[CrossStep]:
    rows = []
    facts = birthday.get("write_facts", {})
    freeze = facts.get("freeze", {})
    statuses = {"completed": TaskStatus.SUCCEEDED, "unknown": TaskStatus.NEEDS_ATTENTION,
                "failed": TaskStatus.FAILED}

    def append(step_id, action, fact, *, order_id=None, payment_status=None):
        rows.append(CrossStep(
            step_id=step_id, action=action, status=statuses.get(fact.get("status")),
            operation_id=fact.get("operation_id"), amount_fen=fact.get("amount_fen"),
            result_ref=fact.get("result_ref"), order_id=order_id,
            payment_status=payment_status))

    if freeze:
        append("birthday-freeze", "bank.freeze_funds", freeze)
    remaining = freeze.get("remaining_fen")
    for index, item in enumerate(birthday.get("orders", [])):
        key = _item_key(item)
        order = facts.get(f"order:{key}", {})
        capture = facts.get(f"capture:{key}", {})
        if order:
            # A verified capture is a bank payment fact for this bound order.
            payment = "paid" if capture.get("status") == "completed" else (
                None if capture.get("status") == "unknown" else order.get("payment_status"))
            append(f"birthday-order-{index}", "bank.create_order", order,
                   order_id=order.get("order_id"), payment_status=payment)
        if capture:
            append(f"birthday-capture-{index}", "bank.capture_frozen", capture,
                   order_id=order.get("order_id"),
                   payment_status="paid" if capture.get("status") == "completed" else None)
            if capture.get("status") == "completed":
                remaining = capture.get("remaining_fen")
    released = birthday.get("released")
    if released:
        settled = released["status"] in ("released", "nothing_to_release")
        if released.get("consumed_total_fen") is not None:
            append("birthday-consumed", "bank.get_freeze", {
                "status": "completed", "amount_fen": released["consumed_total_fen"],
                "result_ref": freeze.get("result_ref"),
            })
        append("birthday-release", "bank.release_frozen", {
            "status": "completed" if settled else "unknown",
            "operation_id": released.get("release_operation_id"),
            "amount_fen": released.get("released_amount_fen") if settled else None,
            "result_ref": freeze.get("result_ref"),
        })
        remaining = released.get("remaining_fen") if settled else None
    unknown = any(row.status is TaskStatus.NEEDS_ATTENTION for row in rows)
    if freeze and freeze.get("status") != "failed":
        # This read row reports the latest bank-returned remainder, not cap minus
        # basket arithmetic. In-flight writes invalidate a current balance claim.
        append("birthday-remaining", "bank.get_freeze", {
            "status": "unknown" if unknown else "completed",
            "amount_fen": None if unknown else remaining,
            "result_ref": freeze.get("result_ref"),
        })
    return rows
