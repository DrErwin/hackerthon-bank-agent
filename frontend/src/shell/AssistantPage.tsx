import { useEffect, useMemo, useRef, useState } from "react";
import type { MessageView } from "../contracts";
import { Composer, ExpiredBanner, MessageBubble, SafetyRail, TopBar, TypingBubble } from "./components/Chrome";
import { Notice } from "./components/Primitives";
import { TaskBlock } from "./components/TaskBlock";
import { businessPayload } from "./components/BusinessCards";
import type { SlotRegistry } from "./slots";
import type { ShellDataSource, TaskEnvelope } from "./types";
import { useConversation } from "./useConversation";

import { buildTimeline, inputPrompt } from "./presentation";
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
  const [replyChoice, setReplyChoice] = useState<string | null>(null);
  const timeline = useMemo(() => buildTimeline(messages, tasks, conversation.cardLinks), [messages, tasks, conversation.cardLinks]);
  const latestTaskId = timeline.filter((item) => item.type === "task").at(-1)?.envelope.task.task_id;
  const primarySlot = slots.slots[0];
  const exampleHints = slots.slots.flatMap((slot) => slot.exampleHints ?? []);
  const inputTasks = [...tasks.values()].filter(({ task }) =>
    task.status === "waiting_input" && task.interaction?.kind === "input"
    && task.allowed_actions.includes("provide_input") && !task.recovery_required
    && !conversation.bootRecovery.has(task.task_id));
  const choice = replyChoice === "chat" ? "chat"
    : inputTasks.some(({ task }) => task.task_id === replyChoice) ? replyChoice!
    : inputTasks.length === 1 ? inputTasks[0].task.task_id : inputTasks.length > 1 ? "" : "chat";
  const replyTask = inputTasks.find(({ task }) => task.task_id === choice)?.task;
  const pendingApproval = [...tasks.values()].filter(({ task }) => task.status === "waiting_approval").length;
  const finished = [...tasks.values()].filter(({ task }) => isTerminal(task)).length;

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

  function renderChild(id: string) {
    const envelope = tasks.get(id);
    if (!envelope) return <p role="status">正在读取…</p>;
    return <TaskBlock envelope={envelope} slot={slots.resolve(envelope.module)} origin={source.origin} conversation={conversation} />;
  }

  async function send(text: string) {
    pinned.current = true;
    if (pendingMessage) return actions.send(text);
    if (replyTask) return actions.provideText(replyTask, text);
    if (!choice) return false;
    return actions.send(text);
  }

  return (
    <div className="sh-root">
      <a className="sh-skip" href="#sh-main">跳到对话内容</a>
      <TopBar title="AI 银行助手" connected={connected} expired={expired} origin={source.origin} userDisplay={session?.user_display ?? null} />
      {expired && <ExpiredBanner onReenter={() => void actions.reenter()} />}
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
              {exampleHints.length > 0 && (
                <p className="sh-examples">可以这样说：{exampleHints.map((hint) => "「" + hint + "」").join("、")}</p>
              )}
            </article>
            {booting && <p className="sh-hint" role="status">正在读取对话记录…</p>}
            {timeline.map((item) => item.type === "message"
              ? <MessageBubble key={item.message.message_id} message={item.message} />
              : <TaskRecord key={item.envelope.task.task_id} task={item.envelope.task} messages={item.messages}
                  latest={item.envelope.task.task_id === latestTaskId}
                  hasActiveChild={conversation.cardLinks.some((link) => {
                    const child = tasks.get(link.childId)?.task;
                    return link.parentId === item.envelope.task.task_id && child && (!isTerminal(child) || child.status === "failed" || child.recovery_required);
                  })}>
                  <TaskBlock envelope={item.envelope} slot={slots.resolve(item.envelope.module)}
                    origin={source.origin} conversation={conversation} renderChild={renderChild} />
                </TaskRecord>)}
            {awaitingReply && <TypingBubble />}
            {pageError && <Notice tone="warning" title="提示">{pageError}</Notice>}
          </div>
        </main>

        </div>
      </div>
      {awayFromLatest && <button type="button" className="sh-back-latest" onClick={jumpToLatest}>回到最新消息 ↓</button>}
      <SafetyRail />
      {inputTasks.length > 0 && (
        <div className="sh-reply-target">
          <label htmlFor="sh-reply-task">继续哪项办理</label>
          <select id="sh-reply-task" value={choice}
            disabled={sending || awaitingReply || Boolean(replyTask && conversation.busy[replyTask.task_id]) || Boolean(pendingMessage)}
            onChange={(event) => setReplyChoice(event.target.value)}>
            {!choice && <option value="">请先选择要继续的办理</option>}
            {inputTasks.map(({ task }, index) => <option key={task.task_id} value={task.task_id}>办理 {index + 1}：{inputPrompt(task)}</option>)}
            <option value="chat">发起新问题</option>
          </select>
        </div>
      )}
      <Composer
        disabled={expired || booting || !conversation.thread || !choice || awaitingReply}
        sending={sending || Boolean(replyTask && conversation.busy[replyTask.task_id])}
        pendingText={pendingMessage?.text ?? null}
        voiceDemoText={primarySlot?.voiceDemoText}
        onSend={send}
      />
    </div>
  );
}
