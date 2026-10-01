import { useCallback, useEffect, useRef, useState } from "react";
import { API_MODE, administratorUrl, apiErrorMessage, connectToThread, get, hasEnteredDemo, markEnteredDemo, post, ApiError } from "./api";
import type { MessageAccepted, MessageView, Page, SessionView, StreamEvent, TaskView, ThreadView } from "./contracts";
import AdminPage from "./AdminPage";
import TaskCard from "./TaskCard";

function makeRequestId(): string {
  return crypto.randomUUID();
}

function statusError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

function mergeMessages(current: MessageView[], incoming: MessageView[]): MessageView[] {
  const byId = new Map(current.map((message) => [message.message_id, message]));
  for (const message of incoming) byId.set(message.message_id, message);
  return [...byId.values()].sort((left, right) => {
    const timeOrder = left.created_at.localeCompare(right.created_at);
    if (timeOrder !== 0) return timeOrder;
    if (left.role !== right.role) return left.role === "user" ? -1 : 1;
    return left.message_id.localeCompare(right.message_id);
  });
}

function mergeTaskList(current: TaskView[], incoming: TaskView[]): TaskView[] {
  const byId = new Map(current.map((task) => [task.task_id, task]));
  for (const task of incoming) {
    const previous = byId.get(task.task_id);
    if (!previous || task.task_revision >= previous.task_revision) byId.set(task.task_id, task);
  }
  return [...byId.values()].sort((left, right) => left.snapshot_at.localeCompare(right.snapshot_at));
}

function mergeOneTask(current: TaskView[], incoming: TaskView): TaskView[] {
  return mergeTaskList(current, [incoming]);
}

function DemoRibbon() {
  if (API_MODE !== "contract-demo") return null;
  return (
    <div className="demo-ribbon" role="status">
      <strong>契约测试响应</strong>
      <span>页面里的回复、验证、人脸和银行结果均为模拟数据，不会调用真实银行。</span>
    </div>
  );
}

function UserGate(props: {
  expired: boolean;
  loading: boolean;
  error: string;
  onEnter: () => void;
  onRetry: () => void;
}) {
  return (
    <main className="gate-page">
      <DemoRibbon />
      <section className="gate-card">
        <div className="brand-mark" aria-hidden="true">银</div>
        <p className="eyebrow">AI Banking Agent</p>
        <h1>银行智能助理</h1>
        <p className="gate-copy">
          {props.expired ? "演示登录已过期。请点击重新进入，再查看原任务的当前状态。" : "正在连接本机演示会话。"}
        </p>
        {props.error && <p className="notice notice-error" role="alert">{props.error}</p>}
        <div className="button-row">
          <button className="button button-primary button-large" onClick={props.onEnter} disabled={props.loading}>
            {props.loading ? "正在进入…" : props.expired ? "重新进入" : "进入演示"}
          </button>
          <button className="button button-secondary button-large" onClick={props.onRetry} disabled={props.loading}>
            检查连接
          </button>
        </div>
        <p className="small-help">聊天用于表达需求。验证码和完整收款账号请使用专用入口。</p>
      </section>
    </main>
  );
}

export default function App() {
  if (window.location.pathname === "/admin") return <AdminPage />;
  return <UserPage />;
}

function UserPage() {
  const [session, setSession] = useState<SessionView | null>(null);
  const [expired, setExpired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [gateError, setGateError] = useState("");
  const [threads, setThreads] = useState<ThreadView[]>([]);
  const [activeThread, setActiveThread] = useState<ThreadView | null>(null);
  const [messages, setMessages] = useState<MessageView[]>([]);
  const [tasks, setTasks] = useState<TaskView[]>([]);
  const [draft, setDraft] = useState("");
  const [chatError, setChatError] = useState("");
  const [pendingMessage, setPendingMessage] = useState<{ id: string; text: string; threadId: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [acceptedMessage, setAcceptedMessage] = useState("");
  const [connected, setConnected] = useState(false);
  const didInitialize = useRef(false);
  const eventSequence = useRef(0);

  const expireSession = useCallback(() => {
    setSession(null);
    setExpired(true);
    setConnected(false);
    setGateError("演示登录已过期，请重新进入后查看任务状态。");
  }, []);

  const loadWorkspace = useCallback(async () => {
    const result = await get<Page<ThreadView>>("/threads?limit=100");
    let available = result.items;
    if (available.length === 0) {
      const created = await post<ThreadView>("/threads", { request_id: makeRequestId() });
      available = [created];
    }
    setThreads(available);
    const selected = available[available.length - 1];
    setActiveThread(selected);
  }, []);

  const enterSession = useCallback(async () => {
    setLoading(true);
    setGateError("");
    try {
      const entered = await post<SessionView>("/session/enter", { request_id: makeRequestId() });
      if (entered.role !== "user") throw new ApiError(403, "ACCESS_DENIED", "普通演示入口未授予用户会话。");
      markEnteredDemo();
      setSession(entered);
      setExpired(false);
      await loadWorkspace();
    } catch (error) {
      if (statusError(error) && error.status === 401) expireSession();
      else setGateError(apiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [expireSession, loadWorkspace]);

  const checkSession = useCallback(async () => {
    setLoading(true);
    setGateError("");
    try {
      const current = await get<SessionView>("/session");
      if (current.role !== "user") {
        throw new ApiError(403, "ACCESS_DENIED", "当前地址使用管理员会话。请返回普通演示入口。");
      }
      setSession(current);
      setExpired(false);
      await loadWorkspace();
    } catch (error) {
      if (statusError(error) && error.status === 401) {
        if (!hasEnteredDemo()) await enterSession();
        else {
          setExpired(true);
          setGateError("演示登录已过期，请点击重新进入。");
        }
      } else setGateError(apiErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [enterSession, loadWorkspace]);

  useEffect(() => {
    if (didInitialize.current) return;
    didInitialize.current = true;
    void checkSession();
  }, [checkSession]);

  const refreshThread = useCallback(async (threadId: string) => {
    try {
      const [messagePage, taskPage] = await Promise.all([
        get<Page<MessageView>>("/threads/" + encodeURIComponent(threadId) + "/messages?limit=100"),
        get<Page<TaskView>>("/tasks?thread_id=" + encodeURIComponent(threadId) + "&limit=100"),
      ]);
      setMessages((current) => mergeMessages(current, messagePage.items));
      setTasks((current) => mergeTaskList(current, taskPage.items));
    } catch (error) {
      if (statusError(error) && error.status === 401) expireSession();
      else setChatError(apiErrorMessage(error));
    }
  }, [expireSession]);

  useEffect(() => {
    if (!session || !activeThread) return;
    let previousConnection = false;
    let hasConnected = false;
    const unsubscribe = connectToThread(
      activeThread.thread_id,
      (event: StreamEvent) => {
        eventSequence.current += 1;
        if (event.event_type === "message_completed") {
          setMessages((current) => mergeMessages(current, [event.payload as MessageView]));
          setAcceptedMessage("");
        } else if (event.event_type === "task_updated") {
          const task = event.payload as TaskView;
          setTasks((current) => mergeOneTask(current, task));
          setAcceptedMessage("");
        } else if (event.event_type === "session_expired") {
          expireSession();
        } else if (event.event_type === "stream_error") {
          const payload = event.payload as { reason?: string };
          setChatError(payload.reason ?? "事件连接暂时中断。页面会通过任务快照补齐状态。");
        }
      },
      (isConnected) => {
        setConnected(isConnected);
        if (isConnected && hasConnected && !previousConnection) {
          void refreshThread(activeThread.thread_id);
        }
        if (isConnected) hasConnected = true;
        previousConnection = isConnected;
      },
    );
    void refreshThread(activeThread.thread_id);
    return unsubscribe;
  }, [activeThread, expireSession, refreshThread, session]);

  function chooseThread(thread: ThreadView) {
    if (thread.thread_id === activeThread?.thread_id) return;
    setMessages([]);
    setTasks([]);
    setChatError("");
    setActiveThread(thread);
  }

  async function createThread() {
    setChatError("");
    try {
      const created = await post<ThreadView>("/threads", { request_id: makeRequestId() });
      setThreads((current) => [...current, created]);
      setMessages([]);
      setTasks([]);
      setActiveThread(created);
    } catch (error) {
      if (statusError(error) && error.status === 401) expireSession();
      else setChatError(apiErrorMessage(error));
    }
  }

  async function refreshCurrentThread() {
    if (activeThread) await refreshThread(activeThread.thread_id);
  }

  async function sendMessage() {
    if (!activeThread || sending) return;
    if (pendingMessage && pendingMessage.threadId !== activeThread.thread_id) {
      setChatError("上一条消息的发送结果尚未确定。请切回原对话后重试，不会把这条消息发送到当前对话。");
      return;
    }
    const pending = pendingMessage ?? { id: makeRequestId(), text: draft.trim(), threadId: activeThread.thread_id };
    if (!pending.text.trim()) return;
    setPendingMessage(pending);
    setSending(true);
    setChatError("");
    const sequenceBeforeSend = eventSequence.current;
    try {
      const result = await post<MessageAccepted>("/threads/" + encodeURIComponent(pending.threadId) + "/messages", {
        request_id: pending.id,
        text: pending.text,
      });
      setPendingMessage(null);
      setDraft("");
      if (sequenceBeforeSend === eventSequence.current) {
        setAcceptedMessage("消息已受理；任务编号可能稍后出现。HTTP 受理不代表交易成功。");
      }
      if (result.task_id) await refreshThread(pending.threadId);
    } catch (error) {
      if (statusError(error) && error.status === 401) expireSession();
      else setChatError(apiErrorMessage(error) + "再次发送会沿用同一个请求编号。");
    } finally {
      setSending(false);
    }
  }

  function setTaskFromCard(task: TaskView) {
    setTasks((current) => mergeOneTask(current, task));
  }

  function setModificationDraft(text: string) {
    setDraft(text);
    setChatError("原确认单已取消。修改要求已放入聊天框，请核对并点击发送；发送会创建新的处理请求。");
  }

  const pendingThread = pendingMessage
    ? threads.find((thread) => thread.thread_id === pendingMessage.threadId)
    : null;
  const retryPendingOnActiveThread = !pendingMessage || activeThread?.thread_id === pendingMessage.threadId;

  if (!session) {
    return <UserGate expired={expired} loading={loading} error={gateError} onEnter={() => void enterSession()} onRetry={() => void checkSession()} />;
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <DemoRibbon />
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">银</div>
          <div>
            <p className="eyebrow">本机演示</p>
            <h1>银行智能助理</h1>
          </div>
        </div>
        <div className="topbar-actions">
          <div className="identity-pill"><span className="online-dot" />{session.user_display}</div>
          <a className="button button-secondary" href={administratorUrl({})}>管理员入口</a>
        </div>
      </header>

      <div className="workspace">
        <aside className="thread-rail" aria-label="对话列表">
          <div className="rail-heading">
            <h2>对话</h2>
            <button className="icon-button" onClick={() => void createThread()} aria-label="新建对话" title="新建对话" disabled={sending}>＋</button>
          </div>
          <button className="button button-new-chat" onClick={() => void createThread()} disabled={sending}>＋ 新对话</button>
          <nav className="thread-list">
            {threads.map((thread) => (
              <button
                key={thread.thread_id}
                className={"thread-item " + (activeThread?.thread_id === thread.thread_id ? "thread-item-active" : "")}
                onClick={() => chooseThread(thread)}
                disabled={sending}
              >
                <span className="thread-item-icon" aria-hidden="true">◷</span>
                <span className="thread-item-text">{thread.title || "新对话"}</span>
              </button>
            ))}
          </nav>
          <div className="rail-bottom">
            <span className={connected ? "connection-label" : "connection-label connection-offline"}>
              <span className="status-dot" />{connected ? "事件连接正常" : "正在重连或等待连接"}
            </span>
            <button className="text-button" onClick={() => void refreshCurrentThread()}>刷新任务状态</button>
          </div>
        </aside>

        <main className="conversation-column" id="main-content" tabIndex={-1}>
          <div className="conversation-heading">
            <div>
              <p className="eyebrow">固定演示用户</p>
              <h2>{activeThread?.title || "新对话"}</h2>
            </div>
            <button className="button button-secondary mobile-new-chat" onClick={() => void createThread()} disabled={sending}>新对话</button>
          </div>
          <div className="conversation-scroll">
            {messages.length === 0 && (
              <section className="welcome-card">
                <div className="welcome-icon" aria-hidden="true">✦</div>
                <p className="eyebrow">您好，{session.user_display}</p>
                <h3>今天有什么需要帮忙？</h3>
                <p>可以用日常说法表达需求。涉及资金的操作会显示独立确认，不会由聊天中的“确认”代替。</p>
                {API_MODE === "contract-demo" && <p className="demo-tip">体验模拟流程：发送“测试转账 500 元”。整个流程使用测试响应。</p>}
              </section>
            )}
            <div className="message-list" aria-live="polite">
              {messages.map((message) => (
                <article className={"message-row message-row-" + message.role} key={message.message_id}>
                  {message.role === "assistant" && <div className="assistant-avatar" aria-hidden="true">银</div>}
                  <div className="message-bubble">
                    <p>{message.text}</p>
                    <time dateTime={message.created_at}>{new Date(message.created_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</time>
                  </div>
                </article>
              ))}
            </div>
            {acceptedMessage && <div className="inline-status" role="status"><span className="status-dot" />{acceptedMessage}</div>}
            {chatError && <div className="notice notice-error" role="alert">{chatError}</div>}
            {tasks.map((task) => (
              <TaskCard
                key={task.task_id}
                task={task}
                onTask={setTaskFromCard}
                onRefresh={refreshCurrentThread}
                onError={(message) => setChatError(message)}
                onSessionExpired={expireSession}
                onModifyDraft={setModificationDraft}
              />
            ))}
          </div>

          <form className="composer" onSubmit={(event) => { event.preventDefault(); void sendMessage(); }}>
            <div className="composer-box">
              <label className="sr-only" htmlFor="chat-input">输入聊天内容</label>
              <textarea
                id="chat-input"
                name="message"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="说说您想办理什么…"
                rows={2}
                required
                autoComplete="off"
                disabled={Boolean(pendingMessage) || sending}
              />
              <button className="send-button" type="submit" disabled={sending || !retryPendingOnActiveThread}>
                {sending ? "发送中…" : pendingMessage ? retryPendingOnActiveThread ? "重试同一请求" : "切回原对话重试" : "发送"}
                <span aria-hidden="true">↗</span>
              </button>
            </div>
            <p className="composer-hint">
              {pendingMessage && !retryPendingOnActiveThread
                ? `上一条消息结果尚未确定，属于“${pendingThread?.title || "原对话"}”。请从左侧切回原对话后重试。`
                : "请勿在聊天里输入验证码或完整账号；它们有专用入口。任务状态以服务端和银行返回为准。"}
            </p>
          </form>
        </main>

        <aside className="help-rail" aria-label="使用提示">
          <section className="help-card">
            <div className="help-card-icon" aria-hidden="true">◎</div>
            <h2>安全办理</h2>
            <p>确认单会单独展示。请逐项核对收款人、金额和费用。</p>
          </section>
          <section className="help-card help-card-muted">
            <div className="help-card-icon" aria-hidden="true">⌁</div>
            <h2>遇到中断</h2>
            <p>刷新后先查看原任务。页面不会因断线自动再次提交操作。</p>
          </section>
          <section className="help-card help-card-muted">
            <div className="help-card-icon" aria-hidden="true">◉</div>
            <h2>查看结果</h2>
            <p>成功或失败以银行结果为准。正在处理和待核实会继续明确显示。</p>
          </section>
        </aside>
      </div>
    </div>
  );
}
