import type { ReactNode } from "react";
import type { CrossTaskView } from "../../contracts";
import {
  crossFacts,
  PLAN_PROMISE,
  PLAN_STOPPED,
  planCounts,
  scenarioTitle,
  stepFacts,
  stepTitle,
} from "../cross";
import { isTerminal, statusLabel } from "../format";
import type { ShellTask } from "../types";
import { FieldList } from "./Primitives";
import { Progress } from "@/components/ui/progress";
import { CircleCheck, CircleAlert, Clock3 } from "lucide-react";

/**
 * The parent plan card: what the arrangement is, which step runs now, and what
 * already happened. It shows the plan's own step states from the server payload
 * and never adds an "approve everything" control: each business still answers on
 * its own task (the current child card is rendered inside the running step).
 *
 * Some cross menus come without a plan body (the server only attaches the view
 * while a step runs or in the cancellation picker); the promise line is then
 * still shown so "adopting a plan" never looks like "everything is approved".
 */
export function CrossPlanCard({ view, task, childTask, renderChild, onQueryChild }: {
  view: CrossTaskView | null;
  task: ShellTask;
  childTask: (taskId: string) => ShellTask | undefined;
  renderChild?: (id: string) => ReactNode;
  onQueryChild?: (taskId: string) => void;
}) {
  const terminal = isTerminal(task);
  const facts = view ? crossFacts(view) : [];
  const counts = view ? planCounts(view) : null;
  const stopped = !terminal && Boolean(view?.stop_reason);
  const lead = terminal ? task.message : stopped ? PLAN_STOPPED : PLAN_PROMISE;
  const stoppedHint = terminal && view?.stop_reason && task.message !== PLAN_STOPPED ? PLAN_STOPPED : null;
  const currentId = view?.interaction_task_id ?? null;
  const activeId = view?.active_step_id ?? null;

  return (
    <section className="sh-card sh-cross-plan" aria-label={scenarioTitle(view) + "安排"}>
      <header className="sh-plan-heading"><h3>{scenarioTitle(view)}</h3>{counts && <span>{counts.done} / {counts.total} 项已办好</span>}</header>
      {!terminal && counts && counts.total > 0 && <Progress value={counts.done / counts.total * 100} aria-label="安排进度" aria-valuetext={"已办好 " + counts.done + " 项，共 " + counts.total + " 项"} />}
      {lead && <p className={terminal ? "sh-lead" : "sh-cross-commit"}>{lead}</p>}
      {view && (
        <ol className="sh-steps sh-cross-steps">
          {view.steps.map((step, index) => {
            const child = step.child_task_id ? childTask(step.child_task_id) : undefined;
            const base = step.status ? statusLabel(step.status, child?.interaction?.kind) : null;
            const label = base && step.status === "needs_attention" && step.error?.source === "security"
              ? { ...base, text: "安全核对暂停" }
              : base;
            const tone = label ? " sh-step-tone-" + label.tone : " sh-step-tone-neutral";
            // Never compare two nulls: an absent interaction id must not highlight
            // every not-yet-planned step as the current one.
            const active = !terminal && ((currentId !== null && step.child_task_id === currentId)
              || (activeId !== null && step.step_id === activeId));
            const currentChild = step.child_task_id && step.child_task_id === currentId ? step.child_task_id : null;
            const earlierChild = step.child_task_id && !currentChild && child && isTerminal(child)
              ? step.child_task_id : null;
            const bank = stepFacts(step);
            return (
              <li key={step.step_id} className={"sh-step sh-cross-step" + tone + (active ? " sh-step-active" : "")}
                aria-current={active ? "step" : undefined}
                aria-label={"第 " + (index + 1) + " 步，" + stepTitle(step) + "，" + (label ? label.text : "待开始")}>
                <div className="sh-step-head">
                  <span className="sh-step-no" aria-hidden="true">{index + 1}</span>
                  <strong>{stepTitle(step)}</strong>
                  <span className="sh-step-state">{label?.tone === "success" ? <CircleCheck aria-hidden="true" /> : label?.tone === "danger" || label?.tone === "warning" ? <CircleAlert aria-hidden="true" /> : <Clock3 aria-hidden="true" />}{label ? label.text : "待开始"}</span>
                </div>
                {(bank.amount || bank.details.length > 0) && (
                  <p className="sh-cross-facts">
                    {bank.amount && <strong>{bank.amount}</strong>}
                    {bank.details.map((detail) => <span key={detail}>{detail}</span>)}
                  </p>
                )}
                {step.error?.reason && step.error.source !== "security" && <p className="sh-inline-error">{step.error.reason}</p>}
                {step.status === "needs_attention" && step.child_task_id && onQueryChild && (
                  <button type="button" className="sh-link-btn" onClick={() => onQueryChild(step.child_task_id!)}>
                    查询这项的结果
                  </button>
                )}
                {currentChild && renderChild && <div className="sh-cross-current">{renderChild(currentChild)}</div>}
                {earlierChild && renderChild && (
                  <details className="sh-disclosure sh-past-step">
                    <summary>查看之前的办理</summary>
                    {renderChild(earlierChild)}
                  </details>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {facts.length > 0 && <FieldList fields={facts} />}
      {stoppedHint && <p className="sh-hint">{stoppedHint}</p>}
      {!terminal && counts && counts.total > 0 && (
        <p className="sh-hint">
          {"已办好 " + counts.done + " 项，共 " + counts.total + " 项。"}
          {activeId && !currentId ? "正在推进下一步。" : ""}
        </p>
      )}
    </section>
  );
}
