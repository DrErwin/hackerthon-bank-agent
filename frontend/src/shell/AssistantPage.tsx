import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { MessageView } from "../contracts";
import { Composer, ExpiredBanner, MessageBubble, SafetyRail, TopBar, TypingBubble } from "./components/Chrome";
import { Notice } from "./components/Primitives";
import { TaskBlock } from "./components/TaskBlock";
import { businessPayload } from "./components/BusinessCards";
import type { SlotRegistry } from "./slots";
import type { ShellDataSource, TaskEnvelope } from "./types";
import { useConversation } from "./useConversation";

import { buildTimeline, needsAttentionInTree, taskTitle } from "./presentation";
import { TaskRecord } from "./components/TaskRecord";
import { isTerminal } from "./format";

export function cardMessageSummary(message: MessageView, tasks: Map<string, TaskEnvelope>): string | undefined {
  if (message.role !== "assistant" || message.task_ids.length !== 1) return undefined;
  const task = tasks.get(message.task_ids[0])?.task;
  const data = task && businessPayload(task);
  if (data && "action" in data && data.action === "list" && data.list_result)
    return "已整理订阅与自动扣款。请在卡片中查看签约、疑似扣款和已退订项目，选择需要办理的一项。";
  return undefined;
}

export function AssistantPage({ source, slots }: { source: ShellDataSource; slots: SlotRegistry }) {
  const conversation = useConversation(source);
  const { messages, tasks, session, expired, connected, booting, pageError, awaitingReply, pendingMessage, sending, actions } = conversation;
  const bodyRef = useRef<HTMLDivElement>(null);
  const [awayFromLatest, setAwayFromLatest] = useState(false);
  const pinned = useRef(true);
  // Cross-linkage children belong inside their parent card, so they never get a
  // record, a "continue" entry or a counter of their own.
  const childIds = conversation.serverChildIds;
  const topTasks = [...tasks.values()].filter(({ task }) => !childIds.has(task.task_id));
  const timeline = useMemo(() => buildTimeline(messages, tasks, conversation.cardLinks, childIds), [messages, tasks, conversation.cardLinks, childIds]);
  const latestTaskId = timeline.filter((item) => item.type === "task").at(-1)?.envelope.task.task_id;
  const exampleHints = slots.slots.flatMap((slot) => slot.exampleHints ?? []);
  const inputTasks = topTasks.filter(({ task }) =>
    task.status === "waiting_input" && task.interaction?.kind === "input"
    && task.allowed_actions.includes("provide_input") && !task.recovery_required
    && !conversation.bootRecovery.has(task.task_id));
  const pendingApproval = topTasks.filter(({ task }) => task.status === "waiting_approval").length;
  const finished = topTasks.filter(({ task }) => isTerminal(task)).length;

  // Expanding a card never moves the reader. Only incoming chat messages follow
  // the bottom, and only while the reader has not scrolled back into history.
  useEffect(() => {
    const body = bodyRef.current;
    if (body && pinned.current) body.scrollTop = body.scrollHeight;
  }, [messages.length, booting]);

  function jumpToLatest() {
    const body = bodyRef.current;
    if (body) body.scrollTop = body.scrollHeight;
    pinned.current = true;
    setAwayFromLatest(false);
  }

  function renderChild(id: string, ancestors = new Set<string>()): ReactNode {
    if (ancestors.has(id)) return <p>关联记录重复，请重新读取办理记录。</p>;
    const envelope = tasks.get(id);
    if (!envelope) return <p role="status">正在读取…</p>;
    return <TaskBlock envelope={envelope} slot={slots.resolve(envelope.module)} origin={source.origin} conversation={conversation}
      renderChild={(child) => renderChild(child, new Set([...ancestors, id]))} />;
  }

  async function send(text: string) {
    pinned.current = true;
    return actions.send(text);
  }

  return (
    <div className="sh-root">
      <a className="sh-skip" href="#sh-main">跳到对话内容</a>
      <TopBar title="AI 银行助手" connected={connected} expired={expired} origin={source.origin} userDisplay={session?.user_display ?? null} />
      {expired && <ExpiredBanner onReenter={() => void actions.reenter()} />}
      {!connected && !booting && !expired && <Notice tone="warning" title="实时更新暂时中断"
        action={<button className="sh-link-btn" onClick={() => void actions.refreshConversation()}>重新读取办理记录</button>}>已有资料仍保留。办理结果请以重新读取的状态为准。</Notice>}
      <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {!booting && `已有 ${messages.filter((message) => message.role === "assistant").length} 条助手回复。${inputTasks.length} 项等您补充，${pendingApproval} 项需要您确认或验证，${finished} 项已结束。请在对话中查看。`}
      </p>
      <div className="sh-body" ref={bodyRef} onScroll={() => {
        const body = bodyRef.current;
        if (!body) return;
        pinned.current = body.scrollHeight - body.scrollTop - body.clientHeight < 96;
        setAwayFromLatest(!pinned.current);
      }}>
        <div className="sh-body-inner">
        <main className="sh-main" id="sh-main" tabIndex={-1}>
          <div className="sh-timeline" >
            <article className="sh-msg sh-msg-assistant">
              <p className="sh-bubble">您好，我是您的银行小助手。您想办点什么？</p>
              <div className="sh-quick-actions" aria-label="常用服务">{[
                ["我要转账", "我要转账"], ["我的账户", "我有哪些账户和余额"], ["我的收款人", "我有哪些收款人"],
                ["查看账单", "查看本月账单"], ["自动扣费", "查看我的订阅和自动扣费"],
              ].map(([label, text]) => <button className="sh-btn sh-btn-secondary" type="button" key={label}
                disabled={expired || booting || sending || awaitingReply || Boolean(pendingMessage)} onClick={() => void send(text)}>{label}</button>)}</div>
              {exampleHints.length > 0 && (
                <p className="sh-examples">可以这样说：{exampleHints.map((hint) => "「" + hint + "」").join("、")}</p>
              )}
            </article>
            {booting && <p className="sh-hint" role="status">正在读取对话记录…</p>}
            {timeline.map((item) => item.type === "message"
              ? <MessageBubble key={item.message.message_id} message={item.message} />
              : <TaskRecord key={item.envelope.task.task_id} task={item.envelope.task} messages={item.messages}
                  latest={item.envelope.task.task_id === latestTaskId}
                  hasActiveChild={conversation.cardLinks.some((link) => link.parentId === item.envelope.task.task_id
                    && needsAttentionInTree(link.childId, tasks, conversation.cardLinks))}>
                  <TaskBlock envelope={item.envelope} slot={slots.resolve(item.envelope.module)}
                    origin={source.origin} conversation={conversation} renderChild={renderChild} />
                </TaskRecord>)}
            {awaitingReply && <><TypingBubble /><button className="sh-link-btn" onClick={() => void actions.refreshConversation()}>查询办理进度</button></>}
            {pageError && <Notice tone="warning" title="提示" action={<button className="sh-link-btn" onClick={() => void (conversation.thread ? actions.refreshConversation() : actions.reenter())}>重新读取</button>}>{pageError}</Notice>}
            {conversation.pageNotice && <p role="status" className="sh-action-feedback">{conversation.pageNotice}</p>}
          </div>
        </main>

        </div>
      </div>
      {awayFromLatest && <button type="button" className="sh-back-latest" onClick={jumpToLatest}>回到最新消息 ↓</button>}
      <SafetyRail />
      {topTasks.some(({ task }) => !isTerminal(task)) && <nav className="sh-pending-nav" aria-label="正在办理">
        <span>继续办理：</span>{topTasks.filter(({ task }) => !isTerminal(task)).map(({ task }) =>
          <button type="button" className="sh-link-btn" key={task.task_id} onClick={() => {
            const target = document.getElementById("task-" + task.task_id);
            let ancestor = target?.parentElement;
            while (ancestor) {
              if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
              ancestor = ancestor.parentElement;
            }
            target?.scrollIntoView({ block: "center" }); target?.focus();
          }}>{taskTitle(task)}</button>)}
      </nav>}
      <Composer
        disabled={expired || booting || !conversation.thread || awaitingReply}
        sending={sending}
        pendingText={pendingMessage?.text ?? null}
        onSend={send}
      />
    </div>
  );
}
