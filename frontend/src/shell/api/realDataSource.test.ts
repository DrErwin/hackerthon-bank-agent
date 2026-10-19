import { afterEach, describe, expect, it, vi } from "vitest";
import type { ConfirmationView, VerificationView } from "../../contracts";
import { createRealDataSource } from "./realDataSource";
import { restoreServerRecordHistory } from "../useConversation";

function response(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(status >= 400 ? data : { data }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("real shell data source", () => {
  it("restores confirmation and verification records in server creation order", () => {
    const confirmation = (id: string, created_at: string): ConfirmationView => ({
      confirmation_id: id,
      task_id: "task-1",
      confirmation_version: 1,
      display_fields: [{ name: "amount", label: "金额", value_text: "¥500.00" }],
      created_at,
      expires_at: "2026-10-16T01:00:00Z",
      decision: "approved" as const,
    });
    const verification = (id: string, created_at: string): VerificationView => ({
      challenge_id: id,
      task_id: "task-1",
      created_at,
      summary: null,
      required_methods: ["code" as const],
      code_expires_at: "2026-10-16T01:00:00Z",
      face_started_at: null,
      face_expires_at: null,
      code_result: "failed" as const,
      face_result: "not_required" as const,
      challenge_status: "failed" as const,
      consecutive_code_failures: 1,
    });

    const restored = restoreServerRecordHistory([], {
      task_id: "task-1",
      confirmations: [
        confirmation("confirmation-1", "2026-10-16T00:00:01Z"),
        confirmation("confirmation-2", "2026-10-16T00:00:03Z"),
      ],
      verifications: [
        verification("verification-1", "2026-10-16T00:00:02Z"),
        verification("verification-2", "2026-10-16T00:00:04Z"),
      ],
    });

    expect(restored.map((entry) => entry.id)).toEqual([
      "confirmation-1", "verification-1", "confirmation-2", "verification-2",
    ]);
  });

  it("loads server-owned confirmation and verification history through F39", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      task_id: "task/with space",
      confirmations: [{ confirmation_id: "confirmation-1" }],
      verifications: [{ challenge_id: "verification-1" }],
    }));
    vi.stubGlobal("fetch", fetch);

    const records = await createRealDataSource().listTaskRecords("task/with space");

    expect(records.task_id).toBe("task/with space");
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/tasks/task%2Fwith%20space/records",
      expect.objectContaining({ method: "GET", credentials: "include", cache: "no-store" }),
    );
  });

  it("preserves the server ownership denial instead of falling back to local history", async () => {
    const fetch = vi.fn().mockResolvedValue(response({
      error: { code: "NOT_FOUND", reason: "当前用户范围内找不到该记录。" },
    }, 404));
    vi.stubGlobal("fetch", fetch);

    await expect(createRealDataSource().listTaskRecords("someone-else-task")).rejects.toMatchObject({
      status: 404,
      code: "NOT_FOUND",
    });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("sends mutations to the existing task with caller-provided idempotency ids", async () => {
    const fetch = vi.fn().mockImplementation(async () => response({ task_id: "task-1", module: "transfer" }));
    vi.stubGlobal("fetch", fetch);
    const source = createRealDataSource();

    await source.resumeTask("task-1", { request_id: "request-1" });
    await source.answerConfirmation("confirmation-1", {
      request_id: "request-2",
      confirmation_version: 3,
      choice: "approve",
    });

    expect(fetch).toHaveBeenNthCalledWith(1, "/api/v1/tasks/task-1/resume", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ request_id: "request-1" }),
    }));
    expect(fetch).toHaveBeenNthCalledWith(2, "/api/v1/confirmations/confirmation-1/answer", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ request_id: "request-2", confirmation_version: 3, choice: "approve" }),
    }));
  });
});
