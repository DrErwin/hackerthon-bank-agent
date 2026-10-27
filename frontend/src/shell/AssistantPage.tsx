import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { MessageView } from "../contracts";
import { Composer, ExpiredBanner, MessageBubble, TopBar, TypingBubble } from "./components/Chrome";
import { Notice } from "./components/Primitives";
import { TaskBlock } from "./components/TaskBlock";
import { businessPayload } from "./components/BusinessCards";
import type { SlotRegistry } from "./slots";
import type { ShellDataSource, TaskEnvelope } from "./types";
import { useConversation } from "./useConversation";

import { buildTimeline, needsAttentionInTree, taskTitle } from "./presentation";
import { TaskRecord } from "./components/TaskRecord";
import { isTerminal, taskStatusLabel } from "./format";
import { ConversationStarters, ConversationTools } from "./components/ConversationTools";
import { DetailsDrawer } from "./components/DetailsDrawer";
import { History, ArrowUpRight } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function cardMessageSummary(message: MessageView, tasks: Map<string, TaskEnvelope>): string | undefined {
  if (message.role !== "assistant" || message.task_ids.length !== 1) return undefined;
  const task = tasks.get(message.task_ids[0])?.task;
  const data = task && businessPayload(task);
  if (data && "action" in data && data.action === "list" && data.list_result)
    return "这些是您的自动扣费。点开一项，就能查看或办理。";
  return undefined;
}

export function AssistantPage({ source, slots }: { source: ShellDataSource; slots: SlotRegistry }) {
  const conversation = useConversation(source);
  const { messages, tasks, session, expired, connected, booting, pageError, awaitingReply, pendingMessage, sending, actions } = conversation;
  const bodyRef = useRef<HTMLDivElement>(null);
  const [awayFromLatest, setAwayFromLatest] = useState(false);
  const [largeText, setLargeText] = useState(() => {
    try { return localStorage.getItem("bank-text-size") === "large"; } catch { return false; }
  });
  const [historyFilter, setHistoryFilter] = useState<"all" | "pending">("all");
  const [historyOpen, setHistoryOpen] = useState(false);
  const historyTarget = useRef<string | null>(null);
  const [expandedRecords, setExpandedRecords] = useState<Record<string, boolean>>({});
  const pinned = useRef(true);
  // Cross-linkage children belong inside their parent card, so they never get a
  // record, a "continue" entry or a counter of their own.
  const childIds = conversation.serverChildIds;
  const topTasks = [...tasks.values()].filter(({ task }) => !childIds.has(task.task_id));
  const timeline = useMemo(() => buildTimeline(messages, tasks, conversation.cardLinks, childIds), [messages, tasks, conversation.cardLinks, childIds]);
  const records = timeline.flatMap((item) => item.type === "task" ? [item.envelope] : []);
  const visibleRecords = records.filter(({ task }) => historyFilter === "all" || !isTerminal(task)
    || needsAttentionInTree(task.task_id, tasks, conversation.cardLinks));
  const latestTaskId = timeline.filter((item) => item.type === "task").at(-1)?.envelope.task.task_id;
  const currentTask = topTasks.filter(({ task }) => !isTerminal(task)).at(-1)?.task;
  const currentNeedsReview = currentTask && (currentTask.recovery_required || conversation.bootRecovery.has(currentTask.task_id) || currentTask.status === "needs_attention");
  const canStart = !(expired || booting || sending || awaitingReply || pendingMessage);
  const inputTasks = [...tasks.values()].filter(({ task }) =>
    task.status === "waiting_input" && task.interaction?.kind === "input"
    && task.allowed_actions.includes("provide_input") && !task.recovery_required
    && !conversation.bootRecovery.has(task.task_id));
  // A cross child owns the pending answer while its parent stays "running", so the
  // spoken summary counts every task; records and the pending nav stay parent-level.
  const pendingApproval = [...tasks.values()].filter(({ task }) => task.status === "waiting_approval").length;
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

  function continueTask(id: string) {
    pinned.current = false;
    setAwayFromLatest(true);
    const recordIds = new Set([id]);
    let parentId = conversation.cardLinks.find((link) => link.childId === id)?.parentId;
    while (parentId && !recordIds.has(parentId)) {
      recordIds.add(parentId);
      parentId = conversation.cardLinks.find((link) => link.childId === parentId)?.parentId;
    }
    setExpandedRecords((current) => ({ ...current, ...Object.fromEntries([...recordIds].map((key) => [key, true])) }));
    requestAnimationFrame(() => {
      const target = document.getElementById("task-" + id);
      let ancestor = target?.parentElement;
      while (ancestor) {
        if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
        ancestor = ancestor.parentElement;
      }
      target?.scrollIntoView({ block: "start", behavior: "instant" });
      target?.focus({ preventScroll: true });
    });
  }

  return (
    <div className="sh-root sh-conversation" data-text-size={largeText ? "large" : "standard"}>
      <a className="sh-skip" href="#sh-main">跳到对话内容</a>
      <TopBar title="银行小助手" connected={connected} expired={expired} origin={source.origin} userDisplay={session?.user_display ?? null}
        largeText={largeText} onTextSizeChange={() => {
          setLargeText(!largeText);
          try { localStorage.setItem("bank-text-size", largeText ? "standard" : "large"); } catch { /* The current page still supports large text when storage is unavailable. */ }
          toast(largeText ? "已恢复标准字号" : "文字已放大");
        }}>
        <DetailsDrawer title="办理记录" triggerLabel={<><History aria-hidden="true" />记录</>} open={historyOpen} onOpenChange={setHistoryOpen}
          onCloseAutoFocus={(event) => {
            if (historyTarget.current) { event.preventDefault(); continueTask(historyTarget.current); historyTarget.current = null; }
          }}>
          {records.length > 0 && <div className="sh-history-filter" role="group" aria-label="筛选办理记录">
            <Button variant={historyFilter === "all" ? "secondary" : "ghost"} aria-pressed={historyFilter === "all"} onClick={() => setHistoryFilter("all")}>全部记录</Button>
            <Button variant={historyFilter === "pending" ? "secondary" : "ghost"} aria-pressed={historyFilter === "pending"} onClick={() => setHistoryFilter("pending")}>还没办完</Button>
          </div>}
          {visibleRecords.length === 0 ? <p className="sh-empty">{historyFilter === "pending" ? "当前没有待继续的事项。" : "办过的事情会留在这里，方便您回看。"}</p> : <ol className="sh-history-list">
            {[...visibleRecords].reverse().map(({ task, module }) => <li key={task.task_id}>
              <h3>{taskTitle(task)}</h3><p>{taskStatusLabel(task).text}</p>
              <dl>{(slots.resolve(module).summarize?.(task) ?? []).map((field, i) => <div key={i}><dt>{field.label}</dt><dd>{field.value_text}</dd></div>)}</dl>
              <button className="sh-btn sh-btn-secondary" onClick={() => { historyTarget.current = task.task_id; setHistoryOpen(false); }}>{isTerminal(task) ? "查看这项记录" : task.recovery_required || conversation.bootRecovery.has(task.task_id) || task.status === "needs_attention" ? "查看办理进度" : "继续这项办理"}</button>
            </li>)}
          </ol>}
        </DetailsDrawer>
      </TopBar>
      {currentTask && <nav className="sh-current-task" aria-label="当前办理">
        <button type="button" onClick={() => continueTask(currentTask.task_id)}>
          <span><span className="sh-current-label">{currentNeedsReview ? "待查看" : "正在办"}</span><strong>{taskTitle(currentTask)}</strong></span>
          <span>{currentNeedsReview ? "查看进度" : "接着办"}<ArrowUpRight aria-hidden="true" /></span>
        </button>
      </nav>}
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
            <article className={"sh-welcome" + (messages.length || topTasks.length ? " sh-welcome-compact" : "")}>
              <h2>您好，今天想办什么？</h2>
              {!messages.length && !topTasks.length && <><p>告诉我您的想法，我陪您一步步办。</p>
                <ConversationStarters disabled={!canStart} onChoose={(text) => void send(text)} />
                <p className="sh-hint">也可以在下面直接打字。</p></>}
            </article>
            {booting && <div className="sh-history-loading" role="status"><p className="sh-hint">正在读取对话记录…</p><div aria-hidden="true"><Skeleton /><Skeleton /></div></div>}
            {timeline.map((item) => item.type === "message"
              ? <MessageBubble key={item.message.message_id} message={item.message} cardSummary={cardMessageSummary(item.message, tasks)} />
              : <TaskRecord key={item.envelope.task.task_id} task={item.envelope.task} messages={item.messages}
                  latest={item.envelope.task.task_id === latestTaskId}
                  expanded={expandedRecords[item.envelope.task.task_id]}
                  onExpandedChange={(open) => setExpandedRecords((current) => ({ ...current, [item.envelope.task.task_id]: open }))}
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
      <Composer
        disabled={expired || booting || !conversation.thread || awaitingReply}
        sending={sending}
        pendingText={pendingMessage?.text ?? null}
        onSend={send}
        tools={<ConversationTools disabled={!canStart} onChoose={(text) => void send(text)} />}
      />
      <Toaster />
    </div>
  );
}
