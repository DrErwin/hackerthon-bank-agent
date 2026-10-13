import { isTerminal, taskStatusLabel } from "../format";
import type { BusinessSlot } from "../slots";
import type { DataOrigin, ResultView, TaskEnvelope } from "../types";
import type { Conversation } from "../useConversation";
import { ConfirmationCard } from "./ConfirmationCard";
import { Notice } from "./Primitives";
import { InputCard, NeedsAttentionCard, RecoveryCard, ResultCard, WaitingCard } from "./StatusCards";
import { VerificationCard } from "./VerificationCard";

function adminHref(taskId: string, challengeId: string, roundId: string): string {
  const params = new URLSearchParams({ task_id: taskId, challenge_id: challengeId, demo_round_id: roundId });
  return "/v04/admin?" + params.toString();
}

export function TaskBlock({ envelope, slot, origin, conversation }: {
  envelope: TaskEnvelope;
  slot: BusinessSlot;
  origin: DataOrigin;
  conversation: Conversation;
}) {
  const { task } = envelope;
  const { actions, history, confirmations, verifications, bootRecovery, recovered, expired } = conversation;
  const busyKey = conversation.busy[task.task_id] ?? "";
  const busy = Boolean(busyKey) || expired;
  const facts = slot.summarize?.(task) ?? [];
  const status = taskStatusLabel(task);
  const gated = bootRecovery.has(task.task_id) || task.recovery_required;
  const outcome = recovered.get(task.task_id);
  const entries = history[task.task_id] ?? [];
  const base = "task-" + task.task_id;

  if (gated) {
    return (
      <div className="sh-task" data-task-id={task.task_id}>
        <RecoveryCard
          id={base + "-recovery"}
          facts={facts}
          statusText={status.text}
          reason={task.recovery_reason}
          resolved={false}
          canDiscard={task.allowed_actions.includes("cancel")}
          busy={busy}
          onResume={() => void actions.resume(task)}
          onDiscard={() => void actions.discard(task)}
        />
        {conversation.taskErrors[task.task_id] && <Notice tone="warning" title="刚才的操作没有完成">{conversation.taskErrors[task.task_id]}</Notice>}
      </div>
    );
  }

  const result: ResultView | null = isTerminal(task)
    ? slot.result?.(task) ?? { tone: status.tone, title: status.text, fields: facts, note: task.message }
    : null;
  const interactionActive = !expired && task.status === "waiting_approval" && !task.recovery_required;
  const showTaskCancel = !expired && task.allowed_actions.includes("cancel") && task.interaction?.kind !== "confirmation";

  return (
    <div className="sh-task" data-task-id={task.task_id}>
      {outcome && (
        <RecoveryCard
          id={base + "-recovered"}
          facts={[]}
          statusText=""
          reason={null}
          resolved
          resolvedText={outcome === "discarded" ? "已放弃这次任务，没有提交新的操作。" : undefined}
          canDiscard={false}
          busy
          onResume={() => undefined}
          onDiscard={() => undefined}
        />
      )}
      {entries.map((entry) => {
        const id = base + "-" + entry.id;
        if (entry.kind === "input") {
          return (
            <InputCard
              key={entry.id}
              id={id}
              interaction={entry.interaction}
              active={!expired && task.status === "waiting_input" && task.interaction?.interaction_id === entry.id}
              busy={busy}
              selectedLabel={entry.selectedLabel}
              onSelect={(optionId, label) => void actions.selectOption(task, optionId, label)}
            />
          );
        }
        const isCurrent = interactionActive && task.interaction?.record_ref === entry.id;
        if (entry.kind === "confirmation") {
          const view = confirmations[entry.id];
          if (!view) return <p key={entry.id} className="sh-hint">正在读取确认单…</p>;
          return (
            <ConfirmationCard
              key={entry.id}
              id={id}
              view={view}
              title={slot.confirmTitle ?? "请确认办理内容"}
              emphasize={slot.emphasizeField}
              active={isCurrent}
              canConfirm={task.allowed_actions.includes("confirm")}
              canCancel={task.allowed_actions.includes("cancel")}
              busy={busy}
              extraActions={isCurrent ? slot.confirmationActions?.(task) ?? [] : []}
              onAnswer={(choice) => void actions.answerConfirmation(task, view, choice)}
            />
          );
        }
        const view = verifications[entry.id];
        if (!view) return <p key={entry.id} className="sh-hint">正在读取验证状态…</p>;
        return (
          <VerificationCard
            key={entry.id}
            id={id}
            view={view}
            active={isCurrent}
            canVerify={task.allowed_actions.includes("verify")}
            busy={busy}
            adminHref={origin === "real-api" ? null : adminHref(task.task_id, view.challenge_id, task.demo_round_id)}
            onSubmitCode={(code) => actions.submitCode(task, view, code)}
            onResend={() => void actions.resendCode(task, view)}
            onStartFace={() => void actions.startFace(task, view)}
            onShowDemoCode={() => actions.showDemoCode(view)}
          />
        );
      })}

      {task.status === "running" && <WaitingCard id={base + "-waiting"} message={task.message} facts={facts} />}
      {task.status === "needs_attention" && (
        <NeedsAttentionCard
          id={base + "-attention"}
          facts={facts}
          message={task.message}
          canQuery={!expired && task.allowed_actions.includes("query")}
          busy={busy}
          onQuery={() => void actions.queryResult(task)}
        />
      )}
      {result && <ResultCard id={base + "-result"} view={result} origin={origin} />}
      {task.error && (
        <Notice tone="danger" title={isTerminal(task) ? "原因说明" : "需要注意"}>
          <p>{task.error.reason}</p>
          {slot.errorHint?.(task.error, task)}
        </Notice>
      )}
      {task.cancel_requested && <Notice tone="warning" title="已收到停止请求">已经提交的操作仍以银行结果为准，我会继续显示原操作的状态。</Notice>}
      {conversation.taskErrors[task.task_id] && (
        <Notice
          tone="warning"
          title="刚才的操作没有完成"
          action={<button type="button" className="sh-link-btn" onClick={() => void actions.refreshTask(task.task_id)}>刷新这项任务的状态</button>}
        >
          {conversation.taskErrors[task.task_id]}
        </Notice>
      )}
      {showTaskCancel && (
        <button type="button" className="sh-btn sh-btn-quiet" disabled={busy} onClick={() => void actions.cancel(task)}>取消这次办理</button>
      )}
    </div>
  );
}
