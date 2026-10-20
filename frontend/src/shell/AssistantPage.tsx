import { useEffect, useMemo, useRef, useState } from "react";
import type { MessageView } from "../contracts";
import { Composer, ExpiredBanner, MessageBubble, SafetyRail, TopBar, TypingBubble } from "./components/Chrome";
import { Notice } from "./components/Primitives";
import { TaskBlock } from "./components/TaskBlock";
import type { SlotRegistry } from "./slots";
import type { ShellDataSource, TaskEnvelope } from "./types";
import { useConversation } from "./useConversation";

type TimelineItem = { type: "message"; message: MessageView } | { type: "task"; envelope: TaskEnvelope };

// A task block sits after the last message that references it, so its newest card is the
// thing closest to the composer.
function buildTimeline(messages: MessageView[], tasks: Map<string, TaskEnvelope>): TimelineItem[] {
  const anchor = new Map<string, number>();
  messages.forEach((message, index) => {
    for (const taskId of message.task_ids) if (tasks.has(taskId)) anchor.set(taskId, index);
  });
  const items: TimelineItem[] = [];
  messages.forEach((message, index) => {
    items.push({ type: "message", message });
    for (const [taskId, at] of anchor) if (at === index) items.push({ type: "task", envelope: tasks.get(taskId)! });
  });
  for (const envelope of tasks.values()) {
    if (!anchor.has(envelope.task.task_id)) items.push({ type: "task", envelope });
  }
  return items;
}

export function AssistantPage({ source, slots }: { source: ShellDataSource; slots: SlotRegistry }) {
  const conversation = useConversation(source);
  const { messages, tasks, session, expired, connected, booting, pageError, awaitingReply, pendingMessage, sending, actions } = conversation;
  const bodyRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [preparedDraft, setPreparedDraft] = useState<string | null>(null);
  const timeline = useMemo(() => buildTimeline(messages, tasks), [messages, tasks]);
  const primarySlot = slots.slots[0];
  const exampleHints = slots.slots.flatMap((slot) => slot.exampleHints ?? []);

  // Cards load asynchronously, so follow content growth while the reader is at the bottom.
  useEffect(() => {
    const body = bodyRef.current;
    const content = timelineRef.current;
    if (!body || !content || typeof ResizeObserver === "undefined") return;
    // Only real user scrolling may unpin; layout-driven scroll events must not.
    const atBottom = () => body.scrollHeight - body.scrollTop - body.clientHeight < 96;
    const follow = () => {
      if (pinned.current) body.scrollTop = body.scrollHeight;
    };
    const onScroll = () => {
      if (atBottom()) pinned.current = true;
    };
    const onUserScroll = () => requestAnimationFrame(() => {
      pinned.current = atBottom();
    });
    const onVisible = () => {
      if (document.visibilityState === "visible") follow();
    };
    const observer = new ResizeObserver(follow);
    const userEvents = ["wheel", "touchmove", "keydown"] as const;
    body.addEventListener("scroll", onScroll, { passive: true });
    userEvents.forEach((name) => body.addEventListener(name, onUserScroll, { passive: true }));
    document.addEventListener("visibilitychange", onVisible);
    observer.observe(content);
    return () => {
      body.removeEventListener("scroll", onScroll);
      userEvents.forEach((name) => body.removeEventListener(name, onUserScroll));
      document.removeEventListener("visibilitychange", onVisible);
      observer.disconnect();
    };
  }, []);

  async function send(text: string) {
    pinned.current = true;
    return actions.send(text);
  }

  return (
    <div className="sh-root">
      <a className="sh-skip" href="#sh-main">跳到对话内容</a>
      <TopBar title="AI 银行助手" connected={connected} expired={expired} origin={source.origin} userDisplay={session?.user_display ?? null} />
      {expired && <ExpiredBanner onReenter={() => void actions.reenter()} />}
      <div className="sh-body" ref={bodyRef}>
        <div className="sh-body-inner">
        <main className="sh-main" id="sh-main" tabIndex={-1}>
          <div className="sh-timeline" aria-live="polite" ref={timelineRef}>
            <article className="sh-msg sh-msg-assistant">
              <p className="sh-bubble">您好，我是您的银行小助手。您想办点什么？</p>
              {exampleHints.length > 0 && (
                <p className="sh-examples">可以这样说：{exampleHints.map((hint) => "「" + hint + "」").join("、")}</p>
              )}
            </article>
            {booting && <p className="sh-hint" role="status">正在读取对话记录…</p>}
            {timeline.map((item) => item.type === "message"
              ? <MessageBubble key={item.message.message_id} message={item.message} />
              : (
                <TaskBlock
                  key={item.envelope.task.task_id}
                  envelope={item.envelope}
                  slot={slots.resolve(item.envelope.module)}
                  origin={source.origin}
                  conversation={conversation}
                  onPrepareModification={setPreparedDraft}
                />
              ))}
            {awaitingReply && <TypingBubble />}
            {pageError && <Notice tone="warning" title="提示">{pageError}</Notice>}
          </div>
        </main>
        <SafetyRail />
        </div>
      </div>
      <Composer
        disabled={expired || booting || !conversation.thread}
        sending={sending}
        pendingText={pendingMessage?.text ?? null}
        voiceDemoText={primarySlot?.voiceDemoText}
        onSend={send}
        preparedDraft={preparedDraft}
        onPreparedDraftUsed={() => setPreparedDraft(null)}
      />
    </div>
  );
}
