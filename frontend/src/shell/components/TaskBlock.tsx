import { useState, type ReactNode } from "react";
import { administratorUrl } from "../../api";
import { isTerminal, taskStatusLabel } from "../format";
import type { BusinessSlot } from "../slots";
import type { DataOrigin, DraftChanges, ResultView, TaskEnvelope } from "../types";
import type { Conversation } from "../useConversation";
import { ConfirmationCard } from "./ConfirmationCard";
import { Notice } from "./Primitives";
import { InputCard, NeedsAttentionCard, RecoveryCard, ReportCard, ResultCard, WaitingCard } from "./StatusCards";
import { VerificationCard } from "./VerificationCard";
import { BillCardActions, BillDetailsCard, BusinessCards, businessPayload, billSummary, billDetails } from "./BusinessCards";
import { inputPrompt } from "../presentation";

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
  const [modifying, setModifying] = useState(false);
  const [modifyText, setModifyText] = useState("");
  const [modifyField, setModifyField] = useState<"amount_fen" | "payer_account_id" | "payee_hint">("amount_fen");
  const [modifyError, setModifyError] = useState("");
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
  const links = (conversation.cardLinks ?? []).filter((link) => link.parentId === task.task_id
    && conversation.tasks.has(link.childId));
  const activeChildren = links.filter((link) => {
    const child = conversation.tasks.get(link.childId)?.task;
    return child && (!isTerminal(child) || child.status === "failed" || child.recovery_required);
  }).map((link) => link.childId);

  if (gated) {
    return (
      <div className="sh-task" id={base} data-task-id={task.task_id}>
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

  const report = isTerminal(task) ? slot.report?.(task) ?? null : null;
  const mapped = isTerminal(task) ? slot.result?.(task) ?? null : null;
  const result: ResultView | null = mapped
    ?? (isTerminal(task) && !report ? { tone: status.tone, title: status.text, fields: facts, note: task.message } : null);
  const interactionActive = !expired && task.status === "waiting_approval" && !task.recovery_required;
  const showTaskCancel = !expired && task.allowed_actions.includes("cancel") && task.interaction?.kind !== "confirmation";

  return (
    <div className="sh-task" id={base} data-task-id={task.task_id}>
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
        const isActive = entry.kind === "input"
          ? !expired && task.status === "waiting_input" && task.allowed_actions.includes("provide_input") && task.interaction?.interaction_id === entry.id
          : interactionActive && task.interaction?.record_ref === entry.id;
        const content = (() => {
        const id = base + "-" + entry.id;
        if (entry.kind === "input") {
          return (
            <InputCard
              key={entry.id}
              id={id}
              interaction={isActive ? { ...entry.interaction, prompt: inputPrompt(task) } : entry.interaction}
              active={!expired && task.status === "waiting_input" && task.allowed_actions.includes("provide_input") && task.interaction?.interaction_id === entry.id}
              busy={busy}
              selectedLabel={entry.selectedLabel}
              onSelect={(optionId, label) => void actions.selectOption(task, optionId, label)}
              onSubmitText={(text) => actions.provideText(task, text)}
            />
          );
        }
        const isCurrent = interactionActive && task.interaction?.record_ref === entry.id;
        if (entry.kind === "confirmation") {
          const view = entry.snapshot ?? confirmations[entry.id];
          if (!view) return <p key={entry.id} className="sh-hint">正在读取确认单…</p>;
          const canModify = isCurrent && Boolean(slot.canModifyConfirmation)
            && task.allowed_actions.includes("confirm") && task.allowed_actions.includes("cancel");
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
                  ...(canModify ? [{ label: "修改", onClick: () => setModifying((value) => !value) }] : []),
                ] : []}
                onAnswer={(choice) => void actions.answerConfirmation(task, view, choice)}
              />
              {modifying && canModify && (
                <form className="sh-modify" onSubmit={async (event) => {
                  event.preventDefault();
                  const requested = modifyText.trim();
                  if (!requested) return;
                  let changes: DraftChanges;
                  if (modifyField === "amount_fen") {
                    const amount = Number(requested) * 100;
                    if (!/^\d+(?:\.\d{1,2})?$/.test(requested) || !Number.isSafeInteger(Math.round(amount)) || amount <= 0) {
                      setModifyError("请填写大于零的金额，最多两位小数。");
                      return;
                    }
                    changes = { amount_fen: Math.round(amount) };
                  } else {
                    changes = { [modifyField]: requested };
                  }
                  setModifyError("");
                  if (!await actions.reviseDraft(task, view, changes)) return;
                  setModifying(false);
                  setModifyText("");
                }}>
                  <label htmlFor={id + "-field"}>修改项目</label>
                  <select id={id + "-field"} value={modifyField} disabled={busy}
                    onChange={(event) => { setModifyField(event.target.value as typeof modifyField); setModifyText(""); setModifyError(""); }}>
                    <option value="amount_fen">金额</option>
                    <option value="payer_account_id">付款账户</option>
                    <option value="payee_hint">收款人</option>
                  </select>
                  <label htmlFor={id + "-modify"}>{modifyField === "amount_fen" ? "新的金额（元）" : modifyField === "payer_account_id" ? "新的付款账户编号" : "新的收款人姓名或备注"}</label>
                  <input id={id + "-modify"} value={modifyText} onChange={(event) => setModifyText(event.target.value)}
                    inputMode={modifyField === "amount_fen" ? "decimal" : "text"} autoComplete="off" disabled={busy} required />
                  {modifyError && <p role="alert" className="sh-inline-error">{modifyError}</p>}
                  <p className="sh-hint">其他信息保持不变。修改后旧确认单失效，请核对新的确认内容。</p>
                  <button type="submit" className="sh-btn sh-btn-primary" disabled={busy || !modifyText.trim()}>保存修改并重新核对</button>
                  <button type="button" className="sh-btn sh-btn-secondary" disabled={busy} onClick={() => setModifying(false)}>暂不修改</button>
                </form>
              )}
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
      <BillDetailsCard task={task} demo={origin !== "real-api"} />
      <BusinessCards task={task} busy={busy} enabled={conversation.supportsCardActions}
        links={links} renderChild={renderChild} activeChildren={activeChildren} onAction={(selection) => actions.cardAction(task, selection)} />
      <BillCardActions task={task} busy={busy} enabled={conversation.supportsCardActions} demo={origin !== "real-api"}
        links={links} renderChild={renderChild} activeChildren={activeChildren}
        details={report ? <ReportCard id={base + "-report"} view={report} origin={origin} /> : result ? <ResultCard id={base + "-result"} view={result} origin={origin} /> : null}
        onAction={(selection) => actions.cardAction(task, selection)} />
      {task.error && (task.error.reason !== result?.note || slot.errorHint?.(task.error, task)) && (
        <Notice tone="danger" title={isTerminal(task) ? "原因说明" : "需要注意"}>
          <p>{task.error.reason}</p>
          {slot.errorHint?.(task.error, task)}
        </Notice>
      )}
      {task.cancel_requested && !isTerminal(task) && <Notice tone="warning" title="已收到停止请求">已经提交的操作仍以银行结果为准，我会继续显示原操作的状态。</Notice>}
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
