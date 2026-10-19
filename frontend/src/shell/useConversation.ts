import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api";
import type { ConfirmationView, DemoCodeView, MessageView, SessionView, TaskRecordsView, ThreadView, VerificationView } from "../contracts";
import { isTerminal, newRequestId } from "./format";
import type { HistoryEntry, ShellDataSource, ShellEvent, ShellTask, TaskEnvelope } from "./types";

const ENTERED_KEY = "fe-shell-entered";
const historyKey = (threadId: string) => "fe-shell-history:" + threadId;

export type RecoveryOutcome = "resumed" | "discarded";

function readHistory(threadId: string): Record<string, HistoryEntry[]> {
  try {
    const raw = localStorage.getItem(historyKey(threadId));
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeHistory(threadId: string, history: Record<string, HistoryEntry[]>): void {
  try {
    localStorage.setItem(historyKey(threadId), JSON.stringify(history));
  } catch {
    // History only keeps record ids and option labels; losing it hides old read-only cards.
  }
}

export function restoreServerRecordHistory(existing: HistoryEntry[], records: TaskRecordsView): HistoryEntry[] {
  const inputEntries = existing.filter((entry) => entry.kind === "input");
  const recordEntries = [
    ...records.confirmations.map((item) => ({
      kind: "confirmation" as const,
      id: item.confirmation_id,
      createdAt: item.created_at,
    })),
    ...records.verifications.map((item) => ({
      kind: "verification" as const,
      id: item.challenge_id,
      createdAt: item.created_at,
    })),
  ].sort((left, right) => left.createdAt.localeCompare(right.createdAt) || left.id.localeCompare(right.id));
  return [...inputEntries, ...recordEntries.map(({ kind, id }): HistoryEntry => ({ kind, id }))];
}

function mergeMessages(current: MessageView[], incoming: MessageView[]): MessageView[] {
  const byId = new Map(current.map((message) => [message.message_id, message]));
  for (const message of incoming) byId.set(message.message_id, message);
  return [...byId.values()].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.message_id.localeCompare(b.message_id));
}

function needsRecovery(task: ShellTask): boolean {
  return task.recovery_required || !isTerminal(task);
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0 || error.status >= 500 || error.status === 429) {
      return error.message + " 可以再点一次，会沿用同一个请求编号，不会重复办理。";
    }
    return error.message;
  }
  return "操作没有完成，请刷新状态后再试。";
}

export function useConversation(source: ShellDataSource) {
  const [session, setSession] = useState<SessionView | null>(null);
  const [thread, setThread] = useState<ThreadView | null>(null);
  const [booting, setBooting] = useState(true);
  const [expired, setExpired] = useState(false);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<MessageView[]>([]);
  const [tasks, setTasks] = useState<Map<string, TaskEnvelope>>(new Map());
  const [history, setHistory] = useState<Record<string, HistoryEntry[]>>({});
  const [confirmations, setConfirmations] = useState<Record<string, ConfirmationView>>({});
  const [verifications, setVerifications] = useState<Record<string, VerificationView>>({});
  const [bootRecovery, setBootRecovery] = useState<Set<string>>(new Set());
  const [recovered, setRecovered] = useState<Map<string, RecoveryOutcome>>(new Map());
  const [busy, setBusy] = useState<Record<string, string>>({});
  const [taskErrors, setTaskErrors] = useState<Record<string, string>>({});
  const [pageError, setPageError] = useState("");
  const [pendingMessage, setPendingMessage] = useState<{ id: string; text: string } | null>(null);
  const [sending, setSending] = useState(false);
  const [awaitingReply, setAwaitingReply] = useState(false);

  const inflight = useRef(new Set<string>());
  const pendingIds = useRef(new Map<string, string>());
  const fetched = useRef(new Set<string>());
  const didBoot = useRef(false);
  const loadFlight = useRef<Promise<void> | null>(null);
  const loadAgain = useRef(false);

  const expire = useCallback(() => {
    setExpired(true);
    setConnected(false);
  }, []);

  const upsertTask = useCallback((task: ShellTask, module?: string | null) => {
    setTasks((current) => {
      const previous = current.get(task.task_id);
      if (previous && previous.task.task_revision > task.task_revision) return current;
      const next = new Map(current);
      next.set(task.task_id, { task, module: module ?? previous?.module ?? null });
      return next;
    });
  }, []);

  const loadThread = useCallback(async (markRecovery: boolean) => {
    if (loadFlight.current) {
      loadAgain.current = true;
      await loadFlight.current;
      return;
    }

    const run = (async () => {
      let recovery = markRecovery;
      do {
        loadAgain.current = false;
        const current = await source.ensureThread();
        const [messageList, taskList] = await Promise.all([source.listMessages(current.thread_id), source.listTasks(current.thread_id)]);
        const recordResults = await Promise.all(taskList.map(async ({ task }) => {
          try {
            return await source.listTaskRecords(task.task_id);
          } catch (error) {
            if (error instanceof ApiError && error.status === 401) throw error;
            return null;
          }
        }));
        const recordLists = recordResults.filter((records): records is TaskRecordsView => records !== null);
        setThread(current);
        setMessages((previous) => mergeMessages(recovery ? [] : previous, messageList));
        setTasks((previous) => {
          const next = recovery ? new Map<string, TaskEnvelope>() : new Map(previous);
          for (const envelope of taskList) {
            const existing = next.get(envelope.task.task_id);
            if (!existing || existing.task.task_revision <= envelope.task.task_revision) next.set(envelope.task.task_id, envelope);
          }
          return next;
        });
        setConfirmations((previous) => {
          const next = recovery ? {} : { ...previous };
          for (const records of recordLists) {
            for (const confirmation of records.confirmations) next[confirmation.confirmation_id] = confirmation;
          }
          return next;
        });
        setVerifications((previous) => {
          const next = recovery ? {} : { ...previous };
          for (const records of recordLists) {
            for (const verification of records.verifications) next[verification.challenge_id] = verification;
          }
          return next;
        });
        if (recovery) {
          const restored = readHistory(current.thread_id);
          for (const records of recordLists) {
            restored[records.task_id] = restoreServerRecordHistory(restored[records.task_id] ?? [], records);
          }
          setHistory(restored);
          fetched.current.clear();
          setBootRecovery(new Set(taskList.filter((envelope) => needsRecovery(envelope.task)).map((envelope) => envelope.task.task_id)));
          setRecovered(new Map());
        } else if (recordLists.length > 0) {
          setHistory((previous) => {
            const restored = { ...previous };
            for (const records of recordLists) {
              restored[records.task_id] = restoreServerRecordHistory(restored[records.task_id] ?? [], records);
            }
            return restored;
          });
        }
        recovery = false;
      } while (loadAgain.current);
    })();

    loadFlight.current = run;
    try {
      await run;
    } finally {
      if (loadFlight.current === run) loadFlight.current = null;
    }
  }, [source]);

  const enter = useCallback(async () => {
    const entered = await source.enterSession({ request_id: newRequestId() });
    localStorage.setItem(ENTERED_KEY, "yes");
    setSession(entered);
    setExpired(false);
    await loadThread(true);
  }, [loadThread, source]);

  useEffect(() => {
    if (didBoot.current) return;
    didBoot.current = true;
    void (async () => {
      try {
        const current = await source.getSession();
        setSession(current);
        await loadThread(true);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          if (localStorage.getItem(ENTERED_KEY) === "yes") expire();
          else {
            try {
              await enter();
            } catch (enterError) {
              setPageError(errorText(enterError));
            }
          }
        } else setPageError(errorText(error));
      } finally {
        setBooting(false);
      }
    })();
  }, [enter, expire, loadThread, source]);

  const threadId = thread?.thread_id ?? null;

  useEffect(() => {
    if (!threadId || expired) return;
    let hadConnection = false;
    let wasConnected = false;
    const unsubscribe = source.subscribe(
      threadId,
      (event: ShellEvent) => {
        if (event.event_type === "message_completed") {
          const message = event.payload as MessageView;
          setMessages((current) => mergeMessages(current, [message]));
          if (message.role === "assistant") setAwaitingReply(false);
        } else if (event.event_type === "task_updated") {
          upsertTask(event.payload as ShellTask, event.module);
        } else if (event.event_type === "session_expired") {
          expire();
        } else if (event.event_type === "stream_error") {
          setPageError("连接有点不稳定，页面会自动补齐最新状态。");
        }
      },
      (isConnected) => {
        setConnected(isConnected);
        if (isConnected && hadConnection && !wasConnected) void loadThread(false).catch(() => undefined);
        if (isConnected) hadConnection = true;
        wasConnected = isConnected;
      },
    );
    return unsubscribe;
  }, [expire, expired, loadThread, source, threadId, upsertTask]);

  useEffect(() => {
    if (!awaitingReply) return;
    const timer = window.setTimeout(() => setAwaitingReply(false), 15_000);
    return () => window.clearTimeout(timer);
  }, [awaitingReply]);

  // Every interaction the server shows becomes a history entry that stays visible read-only.
  useEffect(() => {
    setHistory((current) => {
      let changed = false;
      const next = { ...current };
      for (const { task } of tasks.values()) {
        const interaction = task.interaction;
        if (!interaction) continue;
        const entries = next[task.task_id] ?? [];
        if (interaction.kind === "input") {
          if (entries.some((entry) => entry.kind === "input" && entry.id === interaction.interaction_id)) continue;
          next[task.task_id] = [...entries, { kind: "input", id: interaction.interaction_id, interaction, selectedLabel: null }];
          changed = true;
        } else if (interaction.record_ref && !entries.some((entry) => entry.id === interaction.record_ref)) {
          next[task.task_id] = [...entries, { kind: interaction.kind, id: interaction.record_ref }];
          changed = true;
        }
      }
      return changed ? next : current;
    });
  }, [tasks]);

  useEffect(() => {
    if (threadId) writeHistory(threadId, history);
  }, [history, threadId]);

  useEffect(() => {
    if (expired) return;
    for (const [taskId, entries] of Object.entries(history)) {
      const task = tasks.get(taskId)?.task;
      if (!task) continue;
      for (const entry of entries) {
        if (entry.kind === "input") continue;
        const isCurrent = task.interaction?.record_ref === entry.id;
        const key = entry.id + ":" + (isCurrent ? task.task_revision : "final");
        if (fetched.current.has(key)) continue;
        fetched.current.add(key);
        const request = entry.kind === "confirmation"
          ? source.getConfirmation(entry.id).then((view) => setConfirmations((current) => ({ ...current, [view.confirmation_id]: view })))
          : source.getVerification(entry.id).then((view) => setVerifications((current) => ({ ...current, [view.challenge_id]: view })));
        request.catch((error: unknown) => {
          fetched.current.delete(key);
          if (error instanceof ApiError && error.status === 401) expire();
        });
      }
    }
  }, [expire, expired, history, source, tasks]);

  const refreshTask = useCallback(async (taskId: string) => {
    try {
      const envelope = await source.getTask(taskId);
      upsertTask(envelope.task, envelope.module);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) expire();
    }
  }, [expire, source, upsertTask]);

  async function act<T>(taskId: string, key: string, call: (requestId: string) => Promise<T>): Promise<T | null> {
    if (expired || inflight.current.has(taskId)) return null;
    inflight.current.add(taskId);
    setBusy((current) => ({ ...current, [taskId]: key }));
    setTaskErrors((current) => ({ ...current, [taskId]: "" }));
    const requestId = pendingIds.current.get(key) ?? newRequestId();
    pendingIds.current.set(key, requestId);
    try {
      const result = await call(requestId);
      pendingIds.current.delete(key);
      return result;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        pendingIds.current.delete(key);
        expire();
        return null;
      }
      const retryable = !(error instanceof ApiError) || error.status === 0 || error.status >= 500 || error.status === 429;
      if (!retryable) pendingIds.current.delete(key);
      setTaskErrors((current) => ({ ...current, [taskId]: errorText(error) }));
      if (error instanceof ApiError && error.status === 409) void refreshTask(taskId);
      return null;
    } finally {
      inflight.current.delete(taskId);
      setBusy((current) => {
        const next = { ...current };
        delete next[taskId];
        return next;
      });
    }
  }

  async function selectOption(task: ShellTask, optionId: string, label: string) {
    const interaction = task.interaction;
    if (!interaction || !task.allowed_actions.includes("provide_input")) return;
    const result = await act(task.task_id, "input:" + interaction.interaction_id + ":" + optionId, (request_id) =>
      source.provideInput(task.task_id, { request_id, interaction_id: interaction.interaction_id, selected_option_id: optionId }));
    if (!result) return;
    setHistory((current) => ({
      ...current,
      [task.task_id]: (current[task.task_id] ?? []).map((entry) =>
        entry.kind === "input" && entry.id === interaction.interaction_id ? { ...entry, selectedLabel: label } : entry),
    }));
    upsertTask(result);
  }

  async function answerConfirmation(task: ShellTask, view: ConfirmationView, choice: "approve" | "cancel"): Promise<boolean> {
    if (!task.allowed_actions.includes(choice === "approve" ? "confirm" : "cancel")) return false;
    const result = await act(task.task_id, "confirmation:" + view.confirmation_id + ":" + view.confirmation_version + ":" + choice, (request_id) =>
      source.answerConfirmation(view.confirmation_id, { request_id, confirmation_version: view.confirmation_version, choice }));
    if (!result) return false;
    setConfirmations((current) => ({ ...current, [view.confirmation_id]: { ...view, decision: choice === "approve" ? "approved" : "cancelled" } }));
    upsertTask(result);
    return true;
  }

  // Codes are never replayed: each submission gets fresh ids, and a lost response is followed by a read.
  async function submitCode(task: ShellTask, view: VerificationView, code: string): Promise<string | null> {
    if (expired || inflight.current.has(task.task_id) || !task.allowed_actions.includes("verify")) return null;
    inflight.current.add(task.task_id);
    setBusy((current) => ({ ...current, [task.task_id]: "code" }));
    setTaskErrors((current) => ({ ...current, [task.task_id]: "" }));
    try {
      const response = await source.submitCode(view.challenge_id, { request_id: newRequestId(), submission_id: newRequestId(), code });
      setVerifications((current) => ({ ...current, [response.verification.challenge_id]: response.verification }));
      upsertTask(response.task);
      if (response.kind === "rejected" && response.verification.challenge_status === "pending") return "验证码不对，请再输一次。";
      return null;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        expire();
        return null;
      }
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
        void refreshTask(task.task_id);
        return error.message;
      }
      try {
        const latest = await source.getVerification(view.challenge_id);
        setVerifications((current) => ({ ...current, [latest.challenge_id]: latest }));
      } catch {
        // The task refresh below still shows whether the challenge moved on.
      }
      void refreshTask(task.task_id);
      return "没有收到验证结果，已为您查询最新状态。验证码不会自动重发。";
    } finally {
      inflight.current.delete(task.task_id);
      setBusy((current) => {
        const next = { ...current };
        delete next[task.task_id];
        return next;
      });
    }
  }

  async function resendCode(task: ShellTask, view: VerificationView) {
    if (!task.allowed_actions.includes("verify")) return;
    const fresh = await act(task.task_id, "resend:" + view.challenge_id, (request_id) => source.resendCode(view.challenge_id, { request_id }));
    if (!fresh) return;
    setVerifications((current) => ({ ...current, [fresh.challenge_id]: fresh }));
    void refreshTask(task.task_id);
  }

  async function startFace(task: ShellTask, view: VerificationView) {
    if (!task.allowed_actions.includes("verify")) return;
    const result = await act(task.task_id, "face:" + view.challenge_id, (request_id) => source.startFace(view.challenge_id, { request_id }));
    if (result) setVerifications((current) => ({ ...current, [result.challenge_id]: result }));
  }

  async function showDemoCode(view: VerificationView): Promise<DemoCodeView | null> {
    try {
      return await source.getDemoCode(view.challenge_id);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) expire();
      return null;
    }
  }

  async function queryResult(task: ShellTask) {
    if (!task.allowed_actions.includes("query")) return;
    const result = await act(task.task_id, "query:" + task.task_id + ":" + task.task_revision, (request_id) => source.queryResult(task.task_id, { request_id }));
    if (result) upsertTask(result);
  }

  function settleRecovery(taskId: string, outcome: RecoveryOutcome) {
    setBootRecovery((current) => {
      const next = new Set(current);
      next.delete(taskId);
      return next;
    });
    setRecovered((current) => new Map(current).set(taskId, outcome));
  }

  async function resume(task: ShellTask) {
    if (task.recovery_required) {
      const result = await act(task.task_id, "resume:" + task.task_id + ":" + task.task_revision, (request_id) => source.resumeTask(task.task_id, { request_id }));
      if (!result) return;
      upsertTask(result);
    }
    settleRecovery(task.task_id, "resumed");
  }

  async function cancel(task: ShellTask): Promise<boolean> {
    if (!task.allowed_actions.includes("cancel")) return false;
    const result = await act(task.task_id, "cancel:" + task.task_id, (request_id) => source.cancelTask(task.task_id, { request_id }));
    if (!result) return false;
    upsertTask(result);
    return true;
  }

  async function discard(task: ShellTask) {
    if (await cancel(task)) settleRecovery(task.task_id, "discarded");
  }

  async function send(text: string): Promise<boolean> {
    if (!thread || sending || expired) return false;
    const pending = pendingMessage ?? { id: newRequestId(), text: text.trim() };
    if (!pending.text) return false;
    setPendingMessage(pending);
    setSending(true);
    setPageError("");
    try {
      await source.sendMessage(thread.thread_id, { request_id: pending.id, text: pending.text });
      setPendingMessage(null);
      setAwaitingReply(true);
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setPendingMessage(null);
        expire();
      } else if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429) {
        setPendingMessage(null);
        setPageError(error.message);
        return error.code === "USE_VERIFICATION_ENDPOINT";
      } else {
        setPageError("消息可能没有发出去。" + errorText(error));
      }
      return false;
    } finally {
      setSending(false);
    }
  }

  async function reenter() {
    setPageError("");
    try {
      await enter();
    } catch (error) {
      setPageError(errorText(error));
    }
  }

  return {
    session,
    thread,
    booting,
    expired,
    connected,
    messages,
    tasks,
    history,
    confirmations,
    verifications,
    bootRecovery,
    recovered,
    busy,
    taskErrors,
    pageError,
    pendingMessage,
    sending,
    awaitingReply,
    actions: { send, selectOption, answerConfirmation, submitCode, resendCode, startFace, showDemoCode, queryResult, resume, discard, cancel, reenter, refreshTask },
  };
}

export type Conversation = ReturnType<typeof useConversation>;
