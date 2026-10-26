import { type ReactNode } from "react";
import { administratorUrl } from "../../api";
import { isTerminal, taskStatusLabel } from "../format";
import type { BusinessSlot } from "../slots";
import type { DataOrigin, ResultView, TaskEnvelope } from "../types";
import type { Conversation } from "../useConversation";
import { ConfirmationCard } from "./ConfirmationCard";
import { DeliveryCard } from "./DeliveryCard";
import { Notice } from "./Primitives";
import { InputCard, NeedsAttentionCard, RecoveryCard, ReportCard, ResultCard, WaitingCard } from "./StatusCards";
import { VerificationCard } from "./VerificationCard";
import { BillCardActions, BillDetailsCard, BusinessCards, businessPayload, billSummary, billDetails } from "./BusinessCards";
import { CrossPlanCard } from "./CrossPlanCard";
import { QUANTITY_HINT } from "../copy";
import { asksForQuantity, CROSS_ANSWER_LABEL, crossPlan } from "../cross";
import { GuidedTransfer, transferDraft } from "./GuidedTransfer";
import { inputPrompt, needsAttentionInTree, taskTitle } from "../presentation";

export function verificationAdminHref(taskId: string, challengeId: string, roundId: string, origin: DataOrigin): string {
  if (origin === "real-api") return administratorUrl({ taskId, challengeId, demoRoundId: roundId });
  const params = new URLSearchParams({ task_id: taskId, challenge_id: challengeId, demo_round_id: roundId });
  return "/v04/admin?" + params.toString();
}

export function verificationAdminLabel(origin: DataOrigin): string {
  return origin === "real-api" ? "打开独立管理员会话处理模拟人脸" : "演示用：在新窗口打开管理员演示入口";
}

export function TaskBlock({ envelope, slot, origin, conversation, renderChild }: {
  envelope: TaskEnvelope;
  slot: BusinessSlot;
  origin: DataOrigin;
  conversation: Conversation;
  renderChild?: (id: string) => ReactNode;
}) {
  const { task } = envelope;
  const { actions, history, confirmations, verifications, bootRecovery, recovered, expired } = conversation;
  const busyKey = conversation.busy[task.task_id] ?? "";
  const busy = Boolean(busyKey) || expired;
  const guidedInput = task.interaction?.kind === "input" && task.interaction.required_fields.length > 0
    && task.interaction.required_fields.every((field) => ["amount_fen", "payer_account_id", "payee_hint"].includes(field));
  const guided = Boolean(conversation.readTransferChoices && transferDraft(task)
    && (guidedInput || task.interaction?.kind === "confirmation"));
  const plan = crossPlan(task);
  // Cross menus sometimes arrive without a plan body (the server only attaches the
  // view while a step runs); the promise line must still show before "adopt".
  const showPlanCard = Boolean(plan) || (task.module === "cross" && !isTerminal(task));
  const facts = slot.summarize?.(task) ?? [];
  const status = taskStatusLabel(task);
  const gated = bootRecovery.has(task.task_id) || task.recovery_required;
  const outcome = recovered.get(task.task_id);
  const entries = history[task.task_id] ?? [];
  const base = "task-" + task.task_id;
  let displayTask = task;
  const seen = new Set<string>();
  while (!seen.has(displayTask.task_id)) {
    seen.add(displayTask.task_id);
    const link = [...(conversation.cardLinks ?? [])].reverse().find((item) => item.parentId === displayTask.task_id
      && ["refresh_query", "bill_range"].includes(item.selection.action)
      && conversation.tasks.get(item.childId)?.task.status === "succeeded");
    if (!link) break;
    displayTask = conversation.tasks.get(link.childId)!.task;
  }
  const displayBusy = busy || Boolean(conversation.busy[displayTask.task_id]);
  const transferTargets = [...conversation.tasks.values()].map((item) => item.task).filter((item) => {
    const data = transferDraft(item);
    return data && !data.operation && !item.recovery_required && !conversation.bootRecovery.has(item.task_id)
      && (item.status === "waiting_input" || item.status === "waiting_approval" && item.interaction?.kind === "confirmation");
  });
  const links = (conversation.cardLinks ?? []).filter((link) => link.parentId === displayTask.task_id
    && conversation.tasks.has(link.childId));
  const activeChildren = links.filter((link) => needsAttentionInTree(link.childId, conversation.tasks, conversation.cardLinks ?? [])).map((link) => link.childId);

  if (gated) {
    return (
      <div className="sh-task" id={base} data-task-id={task.task_id} tabIndex={-1}>
        {/* recovery_reason is an internal code; show the backend's user-facing copy instead. */}
        <RecoveryCard
          id={base + "-recovery"}
          facts={facts}
          statusText={status.text}
          reason={task.message || task.error?.reason || null}
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

  const report = isTerminal(displayTask) ? slot.report?.(displayTask) ?? null : null;
  const mapped = isTerminal(task) ? slot.result?.(task) ?? null : null;
  // A cross parent carries its own per-step receipt inside the plan card, so the
  // generic single-result card must not speak for the whole arrangement.
  const result: ResultView | null = mapped
    ?? (isTerminal(task) && !report && !plan ? { tone: status.tone, title: status.text, fields: facts, note: task.message } : null);
  const interactionActive = !expired && task.status === "waiting_approval" && !task.recovery_required;
  // The delivery step collects controlled facts, so it must not fall through to
  // the generic text box; its own card shows field errors where they belong.
  const deliveryActive = !expired && task.status === "waiting_input"
    && task.allowed_actions.includes("provide_input")
    && task.interaction?.kind === "input" && task.interaction.required_fields.includes("delivery");
  const showTaskCancel = !expired && task.allowed_actions.includes("cancel") && task.interaction?.kind !== "confirmation";

  return (
    <div className="sh-task" id={base} data-task-id={task.task_id} tabIndex={-1}>
      {outcome && (
        <RecoveryCard
          id={base + "-recovered"}
          facts={[]}
          statusText=""
          reason={null}
          resolved
          resolvedText={outcome === "discarded" ? "这次办理已取消。" : undefined}
          canDiscard={false}
          busy
          onResume={() => undefined}
          onDiscard={() => undefined}
        />
      )}
      {guided && <GuidedTransfer task={task} conversation={conversation} busy={busy} />}
      {showPlanCard && <CrossPlanCard view={plan} task={task} renderChild={renderChild}
        childTask={(id) => conversation.tasks.get(id)?.task}
        onQueryChild={(id) => {
          const child = conversation.tasks.get(id)?.task;
          if (child?.allowed_actions.includes("query")) void actions.queryResult(child);
        }} />}
      {busyKey && <p role="status" className="sh-action-feedback">正在处理，请稍候…</p>}
      {conversation.taskNotices?.[task.task_id] && <p role="status" className="sh-action-feedback">{conversation.taskNotices[task.task_id]}</p>}
      {entries.map((entry) => {
        const isActive = entry.kind === "input"
          ? !expired && task.status === "waiting_input" && task.allowed_actions.includes("provide_input") && task.interaction?.interaction_id === entry.id
          : interactionActive && task.interaction?.record_ref === entry.id;
        // The draft and confirmation already retain these facts. Avoid a second
        // field picker and empty historic forms after every guided selection.
        if (conversation.readTransferChoices && transferDraft(task) && entry.kind === "input"
          && entry.interaction.required_fields.length > 0
          && entry.interaction.required_fields.every((field) => ["amount_fen", "payer_account_id", "payee_hint"].includes(field))) return null;
        const content = (() => {
        const id = base + "-" + entry.id;
        if (entry.kind === "input") {
          if (entry.interaction.required_fields.includes("delivery")) {
            return (
              <DeliveryCard
                key={entry.id}
                id={id}
                interaction={isActive ? { ...entry.interaction, prompt: inputPrompt(task) } : entry.interaction}
                active={isActive}
                busy={busy}
                handoff={isActive ? conversation.deliveries[task.task_id] ?? null : null}
                error={isActive ? conversation.taskErrors[task.task_id] ?? "" : ""}
                onSelect={(optionId, label) => void actions.selectOption(task, optionId, label)}
                onSubmit={(fields) => actions.submitDelivery(task, fields)}
                onContinue={() => actions.continueDelivery(task)}
              />
            );
          }
          // A quantity screen asks for a count, so the amount example ("例如 1500 或
          // 1500元") does not belong there; every other menu keeps its own hint.
          const asksQuantity = asksForQuantity(entry.interaction);
          return (
            <InputCard
              key={entry.id}
              id={id}
              interaction={isActive ? { ...entry.interaction, prompt: inputPrompt(task) } : entry.interaction}
              active={isActive}
              busy={busy}
              selectedLabel={entry.selectedLabel}
              onSelect={(optionId, label) => void actions.selectOption(task, optionId, label)}
              onSubmitText={(text) => actions.provideText(task, text)}
              textLabel={asksQuantity ? QUANTITY_HINT : task.module === "cross" && entry.interaction.kind === "input"
                && entry.interaction.options.length < 3 ? CROSS_ANSWER_LABEL : undefined}
              numeric={asksQuantity}
            />
          );
        }
        const isCurrent = interactionActive && task.interaction?.record_ref === entry.id;
        if (entry.kind === "confirmation") {
          const view = entry.snapshot ?? confirmations[entry.id];
          if (!view) return <p key={entry.id} className="sh-hint">正在读取确认单…</p>;
          return (
            <div key={entry.id}>
              <ConfirmationCard
                id={id}
                view={view}
                title={slot.confirmTitle ?? "请确认办理内容"}
                emphasize={slot.emphasizeField}
                active={isCurrent}
                canConfirm={task.allowed_actions.includes("confirm")}
                canCancel={task.allowed_actions.includes("cancel")}
                busy={busy}
                extraActions={isCurrent ? [
                  ...(slot.confirmationActions?.(task) ?? []),
                ] : []}
                options={isCurrent ? task.interaction?.options ?? [] : []}
                onSelectOption={(optionId, label) => void actions.selectOption(task, optionId, label)}
                onAnswer={(choice) => void actions.answerConfirmation(task, view, choice)}
              />

            </div>
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
            adminHref={verificationAdminHref(task.task_id, view.challenge_id, task.demo_round_id, origin)}
            adminLabel={verificationAdminLabel(origin)}
            options={isCurrent ? task.interaction?.options ?? [] : []}
            onSelectOption={(optionId, label) => void actions.selectOption(task, optionId, label)}
            onSubmitCode={(code) => actions.submitCode(task, view, code)}
            onResend={() => void actions.resendCode(task, view)}
            onStartFace={() => void actions.startFace(task, view)}
            onShowDemoCode={() => actions.showDemoCode(view)}
          />
        );
        })();
        return isActive ? <div key={entry.id}>{content}</div> :
          <details key={entry.id} className="sh-disclosure sh-past-step"><summary>{entry.kind === "confirmation" ? "查看之前的确认内容" : entry.kind === "verification" ? "查看之前的验证记录" : "查看之前补充的信息"}</summary>{content}</details>;
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
      {report && !billSummary(task) && <ReportCard id={base + "-report"} view={report} origin={origin} />}
      {result && !businessPayload(task) && !billSummary(task) && !billDetails(task) && <ResultCard id={base + "-result"} view={result} origin={origin} />}
      <BillDetailsCard key={"details-" + displayTask.task_id} task={displayTask} demo={origin !== "real-api"} busy={displayBusy} links={links} renderChild={renderChild} activeChildren={activeChildren}
        onAction={conversation.supportsCardActions ? (selection) => actions.cardAction(displayTask, selection) : undefined} />
      <BusinessCards key={"business-" + displayTask.task_id} task={displayTask} busy={displayBusy} enabled={conversation.supportsCardActions}
        transferTargets={expired ? [] : transferTargets}
        targetBusy={conversation.busy} targetErrors={conversation.taskErrors}
        onChoose={async (target, changes) => {
          const view = target.interaction?.record_ref ? confirmations[target.interaction.record_ref] : undefined;
          if (await actions.reviseDraft(target, view, changes)) {
            const element = document.getElementById("task-" + target.task_id);
            element?.scrollIntoView({ block: "center" }); element?.focus();
          }
        }}
        links={links} renderChild={renderChild} activeChildren={activeChildren} onAction={(selection) => actions.cardAction(displayTask, selection)} />
      <BillCardActions key={"bill-" + displayTask.task_id} task={displayTask} busy={displayBusy} enabled={conversation.supportsCardActions} demo={origin !== "real-api"}
        links={links} renderChild={renderChild} activeChildren={activeChildren}
        details={report ? <ReportCard id={base + "-report"} view={report} origin={origin} /> : result ? <ResultCard id={base + "-result"} view={result} origin={origin} /> : null}
        onAction={(selection) => actions.cardAction(displayTask, selection)} />
      {displayTask.task_id !== task.task_id && <>
        <p className="sh-action-feedback" role="status">已显示重新查询的资料。</p>
        {(conversation.cardLinks ?? []).filter((link) => seen.has(link.parentId) && link.parentId !== displayTask.task_id && !seen.has(link.childId)).map((link) =>
          <details className="sh-disclosure" key={link.childId}
            open={needsAttentionInTree(link.childId, conversation.tasks, conversation.cardLinks ?? []) || link.selection.action === "subscription_cancel"}>
            <summary>之前查询中的办理 · {conversation.tasks.get(link.childId) ? taskTitle(conversation.tasks.get(link.childId)!.task) : "办理记录"}</summary>
            {renderChild?.(link.childId)}
          </details>)}
        <details className="sh-disclosure"><summary>查看上次查询记录</summary>
          <BusinessCards task={task} busy={false} enabled={false} onAction={async () => null} />
          {billSummary(task) && <p>{task.message}</p>}
        </details>
        {conversation.taskErrors[displayTask.task_id] && <Notice tone="warning" title="查询没有完成">{conversation.taskErrors[displayTask.task_id]}</Notice>}
      </>}
      {(conversation.cardLinks ?? []).filter((link) => link.parentId === displayTask.task_id && ["refresh_query", "bill_range"].includes(link.selection.action)
        && conversation.tasks.get(link.childId)?.task.status !== "succeeded").map((link) => <div key={link.childId}>{renderChild?.(link.childId)}</div>)}
      {task.error && (task.error.reason !== result?.note || slot.errorHint?.(task.error, task)) && (
        <Notice tone="danger" title={isTerminal(task) ? "原因说明" : "需要注意"}>
          <p>{task.error.reason}</p>
          {slot.errorHint?.(task.error, task)}
        </Notice>
      )}
      {task.cancel_requested && !isTerminal(task) && <Notice tone="warning" title="已收到停止请求">已经提交的操作仍以银行结果为准，我会继续显示原操作的状态。</Notice>}
      {conversation.taskErrors[task.task_id] && !deliveryActive && (
        <Notice
          tone="warning"
          title="刚才的操作没有完成"
          action={<button type="button" className="sh-link-btn" onClick={() => void actions.refreshTask(task.task_id)}>刷新这项任务的状态</button>}
        >
          {conversation.taskErrors[task.task_id]}
        </Notice>
      )}
      {task.status === "succeeded" && transferDraft(task)?.operation?.operation_status === "succeeded" && <button className="sh-btn sh-btn-secondary" disabled={busy || conversation.sending || conversation.awaitingReply} onClick={() => void actions.send("查询我的账户余额")}>查看最新余额</button>}
      {showTaskCancel && (
        <button type="button" className="sh-btn sh-btn-quiet" disabled={busy} onClick={() => void actions.cancel(task)}>取消这次办理</button>
      )}
    </div>
  );
}
