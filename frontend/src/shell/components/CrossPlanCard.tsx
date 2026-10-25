import type { ReactNode } from "react";
import type { CrossTaskView } from "../../contracts";
import {
  crossFacts,
  PLAN_PROMISE,
  PLAN_STOPPED,
  planCounts,
  scenarioTitle,
  stepTitle,
} from "../cross";
import { isTerminal, statusLabel } from "../format";
import type { ShellTask } from "../types";
import { FieldList } from "./Primitives";

/**
 * The parent plan card: what the arrangement is, which step runs now, and what
 * already happened. It shows the plan's own step states from the server payload
 * and never adds an "approve everything" control: each business still answers on
 * its own task (the current child card is rendered inside the running step).
 */
export function CrossPlanCard({ view, task, childTask, renderChild }: {
  view: CrossTaskView;
  task: ShellTask;
  childTask: (taskId: string) => ShellTask | undefined;
  renderChild?: (id: string) => ReactNode;
}) {
  const terminal = isTerminal(task);
  const counts = planCounts(view);
  const facts = crossFacts(view);
  const stopped = !terminal && Boolean(view.stop_reason);
  const lead = terminal ? task.message : stopped ? PLAN_STOPPED : PLAN_PROMISE;
  const stoppedHint = terminal && view.stop_reason && task.message !== PLAN_STOPPED ? PLAN_STOPPED : null;
  const currentId = view.interaction_task_id;
  const activeId = view.active_step_id;

  return (
    <section className="sh-card sh-cross-plan" aria-label={scenarioTitle(view) + "安排"}>
      {lead && <p className={terminal ? "sh-lead" : "sh-cross-commit"}>{lead}</p>}
      <ol className="sh-steps sh-cross-steps">
        {view.steps.map((step, index) => {
          const label = step.status ? statusLabel(step.status, childTask(step.child_task_id ?? "")?.interaction?.kind) : null;
          const tone = label ? " sh-step-tone-" + label.tone : " sh-step-tone-neutral";
          const active = !terminal && (step.step_id === activeId || step.child_task_id !== undefined && step.child_task_id === currentId);
          return (
            <li key={step.step_id} className={"sh-step sh-cross-step" + tone + (active ? " sh-step-active" : "")}
              aria-current={active ? "step" : undefined}>
              <div className="sh-step-head">
                <span className="sh-step-no" aria-hidden="true">{index + 1}</span>
                <strong>{stepTitle(step)}</strong>
                <span className="sh-step-state">{label ? label.icon + " " + label.text : "待开始"}</span>
              </div>
              {step.error?.reason && <p className="sh-inline-error">{step.error.reason}</p>}
              {step.child_task_id && step.child_task_id === currentId && renderChild && (
                <div className="sh-cross-current">{renderChild(step.child_task_id)}</div>
              )}
            </li>
          );
        })}
      </ol>
      {facts.length > 0 && <FieldList fields={facts} />}
      {stoppedHint && <p className="sh-hint">{stoppedHint}</p>}
      {!terminal && counts.total > 0 && (
        <p className="sh-hint">
          {"已办好 " + counts.done + " 项，共 " + counts.total + " 项。"}
          {view.active_step_id && !currentId ? "正在推进下一步。" : ""}
        </p>
      )}
    </section>
  );
}
