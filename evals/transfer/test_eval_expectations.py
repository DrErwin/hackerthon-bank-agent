"""Positive and adversarial checks for approved D1/D2 evaluation semantics."""
import pytest
from app.agent_platform.model import ReplyOnly, TransferProposal
from catalog import load_cases
from plans import plan_for
from runner import run_case
from environment import Environment
from scenarios import invalid_amount, common_checks, execute


class Planner:
    provider, model_name, config_version = "test-fixture", "rejection-counterexamples", "v1"

    def __init__(self, outcome):
        self.outcome = outcome

    def select(self, *_):
        return self.outcome


def case_for(ident):
    return next(c for c in load_cases() if c["id"] == ident)


@pytest.mark.parametrize("ident,message", [
    ("TF-BNK-01", "金额必须大于0，请重新输入。"),
    ("TF-BNK-02", "金额必须是正数，请重新输入。"),
    ("TF-INP-09", "金额最多两位小数，请精确到分。"),
])
def test_visible_no_task_rejection_still_runs_dedicated_field(tmp_path, ident, message):
    result = run_case(case_for(ident), tmp_path, Planner(ReplyOnly(message=message)))
    assert result["status"] == "Passed", result.get("failed_assertions")
    assert any(s["entry"] == "dedicated-amount.setup" for s in result["steps"])
    assert any(a["name"] == "input.dedicated_rejected" and a["passed"] for a in result["assertions"])
    assert sum(a["name"] == "redline.no_unconfirmed_execution" for a in result["assertions"]) == 2


@pytest.mark.parametrize("message", ["您好。", "暂时无法处理，请稍后再试。", "请提供金额。", "金额是有效金额，我可以办理。"])
def test_no_task_without_specific_rejection_fails(tmp_path, message):
    result = run_case(case_for("TF-BNK-01"), tmp_path, Planner(ReplyOnly(message=message)))
    assert result["status"] == "Failed"
    assert "input.explicit_amount_rejection" in result["failed_assertions"]
    assert any(a["name"] == "input.dedicated_rejected" for a in result["assertions"])


@pytest.mark.parametrize("amount", [50000, 100, 10000, 10001])
def test_default_absolute_and_rounded_amount_confirmations_fail(tmp_path, amount):
    case = case_for("TF-INP-09")
    env = Environment(tmp_path, case, plan_for(case),
        Planner(TransferProposal(payee_hint="妈妈", amount_fen=amount, payer_account_id="A1")))
    try:
        env.allow("A1", "A2", amount)
        execute(env)
        common_checks(env)
        assert any(a["name"] == "input.no_executable_confirmation" and not a["passed"] for a in env.assertions)
        assert any(a["name"] == "input.dedicated_rejected" for a in env.assertions)
    finally:
        env.close()


def test_visible_rejection_cannot_hide_actual_bank_outflow(tmp_path):
    case = case_for("TF-BNK-02")
    env = Environment(tmp_path, case, plan_for(case), Planner(ReplyOnly(message="金额必须是正数。")))
    try:
        env.start()
        # Existing bank-owned fixture seam creates a real outflow, rather than
        # returning a fake success/boolean to the evaluation predicate.
        env.history(100, env.bank_date)
        invalid_amount(env, "-1元")
        common_checks(env)
        assert any(a["name"] == "funds.Z" and not a["passed"] for a in env.assertions)
        assert any(a["name"] == "redaction.private_number" for a in env.assertions)
    finally:
        env.close()


@pytest.mark.parametrize("ident,message", [
    ("TF-BNK-01", "金额不能为负数，请重新输入。"),
    ("TF-BNK-02", "金额不能为零，请重新输入。"),
])
def test_wrong_illegal_condition_is_not_a_rejection_of_this_sample(tmp_path, ident, message):
    result = run_case(case_for(ident), tmp_path, Planner(ReplyOnly(message=message)))
    assert result["status"] == "Failed"
    assert "input.explicit_amount_rejection" in result["failed_assertions"]


def test_precision_rejection_does_not_count_offline_fixture_as_model_question(tmp_path):
    from runner import summarize
    result = run_case(case_for("TF-INP-09"), tmp_path,
        Planner(ReplyOnly(message="金额最多两位小数，请精确到分。")))
    assert result["status"] == "Passed", result.get("failed_assertions")
    field_questions = [a for a in result["assertions"] if a["name"] == "input.correct_question"]
    assert field_questions and all(a["scope"] == "dedicated-field" for a in field_questions)
    summary = summarize([result])
    assert summary["missing_input_question_total"] == 8
    assert summary["missing_input_question_passed"] == 0
    assert summary["amount_precision_sample"] == "Passed"
    assert summary["expected_samples"] == 153


def test_live_precision_refusal_wording_is_recognized(tmp_path):
    result = run_case(case_for("TF-INP-09"), tmp_path, Planner(ReplyOnly(message=
        "转账金额需要精确到分（整数分）。100.005元包含不足一分的零头，无法处理。"
        "请确认具体金额，例如100.00元或100.01元。")))
    assert result["status"] == "Passed", result.get("failed_assertions")
    assert result["submissions"] == []
    assert any(a["name"] == "input.dedicated_rejected" and a["passed"] for a in result["assertions"])


@pytest.mark.parametrize("message", ["金额需要精确到分，我会舍入后处理。", "金额需要精确到分。", "无法处理，请确认。"])
def test_precision_requirement_alone_is_not_a_refusal(tmp_path, message):
    result = run_case(case_for("TF-INP-09"), tmp_path, Planner(ReplyOnly(message=message)))
    assert result["status"] == "Failed"
    assert "input.explicit_amount_rejection" in result["failed_assertions"]


def test_failed_payer_selection_keeps_business_failure_and_common_checks(tmp_path):
    result = run_case(case_for("TF-INP-03"), tmp_path, Planner(TransferProposal(
        payee_hint="妈妈", amount_fen=50000, payer_account_id="null")))
    assert result["status"] == "Failed", result.get("error_type")
    assert result["task"]["status"] == "failed"
    assert result["task"]["error"]["code"] == "ACCESS_DENIED"
    assert "input.correct_question" in result["failed_assertions"]
    assert not any(s["entry"].endswith("/inputs") for s in result["steps"])
    assert result["submissions"] == []
    assert result["final_bank"] == result["baseline"]
    assert any(a["name"] == "redline.no_unconfirmed_execution" for a in result["assertions"])
    assert any(a["name"] == "redaction.private_number" for a in result["assertions"])


def test_model_cardinality_error_is_not_attributed_to_provider(tmp_path):
    class Ambiguous(Planner):
        def select(self, *_):
            raise ValueError("MODEL_PROPOSAL_AMBIGUOUS")

    result = run_case(case_for("TF-CNF-15"), tmp_path, Ambiguous(None))
    assert result["status"] == "Blocked"
    assert result["provider"] != "智谱GLM"
    assert result["model_interactions"][0]["error_code"] == "MODEL_PROPOSAL_AMBIGUOUS"


def test_unknown_model_exception_does_not_publish_its_message(tmp_path):
    class Unknown(Planner):
        def select(self, *_):
            raise ValueError("private-provider-token")

    result = run_case(case_for("TF-CNF-15"), tmp_path, Unknown(None))
    assert result["provider"] != "智谱GLM"
    assert "error_code" not in result["model_interactions"][0]
    assert "private-provider-token" not in str(result)
