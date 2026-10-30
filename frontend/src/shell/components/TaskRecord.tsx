import { useState, type ReactNode } from "react";
import type { MessageView } from "../../contracts";
import { isTerminal, taskStatusLabel, type StatusLabel } from "../format";
import { taskTitle } from "../presentation";
import type { ShellTask } from "../types";

export function TaskRecord({ task, latest, children, hasActiveChild = false, status = taskStatusLabel(task), expanded: controlledExpanded, onExpandedChange }: {
  task: ShellTask; messages: MessageView[]; latest: boolean; children: ReactNode;
  hasActiveChild?: boolean;
  // The whole card's status; defaults to the task's own.
  status?: StatusLabel;
  expanded?: boolean;
  onExpandedChange?: (open: boolean) => void;
}) {
  const [localExpanded, setExpanded] = useState<boolean | null>(null);
  const expanded = controlledExpanded ?? localExpanded;
  const needsAction = hasActiveChild || !isTerminal(task) || task.recovery_required || task.status === "failed" || task.status === "partially_succeeded";
  const open = needsAction || (expanded ?? latest);
  const panelId = "record-" + task.task_id;
  return <article className={"sh-record" + (needsAction ? " sh-record-active" : "")}>
    <button type="button" className="sh-record-heading" aria-expanded={open} aria-controls={panelId}
      onClick={() => { setExpanded(!open); onExpandedChange?.(!open); }} disabled={needsAction}>
      <span className="sh-record-title">{taskTitle(task)}</span>
      <span className={"sh-record-status sh-record-status-" + status.tone}>{status.text}</span>
      {!needsAction && <span className="sh-record-toggle">{open ? "收起" : "展开"}</span>}
    </button>
    <div id={panelId} hidden={!open} className="sh-record-content">
      {children}
    </div>
  </article>;
}
