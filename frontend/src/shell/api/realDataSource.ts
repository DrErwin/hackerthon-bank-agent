import { connectToThread, get, post } from "../../api";
import type {
  ConfirmationView,
  DemoCodeView,
  MessageAccepted,
  MessageView,
  SessionView,
  TaskRecordsView,
  TaskView,
  ThreadView,
  VerificationResponse,
  VerificationView,
} from "../../contracts";
import { getPageItems } from "../../pagination";
import type { ShellDataSource, ShellEvent, ShellTask, ShellVerificationResponse, TaskEnvelope } from "../types";

function envelope(task: TaskView): TaskEnvelope {
  return {
    task: task as ShellTask,
    module: task.module ?? null,
  };
}

export function createRealDataSource(): ShellDataSource {
  return {
    origin: "real-api",

    enterSession: (body) => post<SessionView>("/session/enter", body),
    getSession: () => get<SessionView>("/session"),

    async ensureThread() {
      const threads = await getPageItems<ThreadView>("/threads?limit=100");
      return threads.at(-1) ?? post<ThreadView>("/threads", { request_id: crypto.randomUUID() });
    },

    listMessages: (threadId) =>
      getPageItems<MessageView>("/threads/" + encodeURIComponent(threadId) + "/messages?limit=100"),

    async listTasks(threadId) {
      const tasks = await getPageItems<TaskView>("/tasks?thread_id=" + encodeURIComponent(threadId) + "&limit=100");
      return tasks.map(envelope);
    },

    async getTask(taskId) {
      return envelope(await get<TaskView>("/tasks/" + encodeURIComponent(taskId)));
    },

    listTaskRecords: (taskId) => get<TaskRecordsView>("/tasks/" + encodeURIComponent(taskId) + "/records"),

    sendMessage: (threadId, body) =>
      post<MessageAccepted>("/threads/" + encodeURIComponent(threadId) + "/messages", body),

    provideInput: (taskId, body) =>
      post<ShellTask>("/tasks/" + encodeURIComponent(taskId) + "/inputs", body),

    resumeTask: (taskId, body) =>
      post<ShellTask>("/tasks/" + encodeURIComponent(taskId) + "/resume", body),

    cancelTask: (taskId, body) =>
      post<ShellTask>("/tasks/" + encodeURIComponent(taskId) + "/cancel", body),

    queryResult: (taskId, body) =>
      post<ShellTask>("/tasks/" + encodeURIComponent(taskId) + "/query-result", body),

    getConfirmation: (confirmationId) =>
      get<ConfirmationView>("/confirmations/" + encodeURIComponent(confirmationId)),

    answerConfirmation: (confirmationId, body) =>
      post<ShellTask>("/confirmations/" + encodeURIComponent(confirmationId) + "/answer", body),

    getVerification: (challengeId) =>
      get<VerificationView>("/verifications/" + encodeURIComponent(challengeId)),

    submitCode: async (challengeId, body) => {
      const response = await post<VerificationResponse>(
        "/verifications/" + encodeURIComponent(challengeId) + "/code",
        body,
      );
      return response as ShellVerificationResponse;
    },

    resendCode: (challengeId, body) =>
      post<VerificationView>("/verifications/" + encodeURIComponent(challengeId) + "/resend-code", body),

    getDemoCode: (challengeId) =>
      get<DemoCodeView>("/verifications/" + encodeURIComponent(challengeId) + "/demo-code"),

    startFace: (challengeId, body) =>
      post<VerificationView>("/verifications/" + encodeURIComponent(challengeId) + "/face/start", body),

    subscribe(threadId, onEvent, onConnection) {
      return connectToThread(threadId, (event) => onEvent(event as ShellEvent), onConnection);
    },
  };
}
