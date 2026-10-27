import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { API_MODE, ApiError, apiErrorMessage, get, post, userPageUrl } from "./api";
import type { ManagementOperation, ResetPreview, ResetPreviewRequest, ResetRequest, SessionView } from "./contracts";

type ResetRecord = {
  previewRequest: ResetPreviewRequest;
  preview?: ResetPreview;
  request?: ResetRequest;
  operation?: ManagementOperation;
};
const storageKey = "bank-admin-demo-reset-v1";

function savedReset(): { record: ResetRecord | null; error: string } {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return { record: null, error: "" };
    const record = JSON.parse(raw) as ResetRecord;
    if (!record.previewRequest?.request_id || !record.previewRequest.demo_round_id
        || (record.preview && !Array.isArray(record.preview.effects))
        || (record.request && (!record.request.request_id || !record.request.reset_confirmation_id))
        || (record.operation && !record.operation.management_operation_id)) throw new Error();
    return { record, error: "" };
  } catch {
    return { record: null, error: "本机重置记录无法读取。请保留现场，由管理员核对原管理操作；本页暂不创建另一笔重置。" };
  }
}

const phases: Record<string, string> = {
  waiting_inflight: "等待正在执行的操作结束",
  resetting_bank: "恢复银行演示数据",
  resetting_application: "切换应用轮次",
  resetting_memory: "恢复预置记忆",
  resetting_clock: "恢复逻辑起点",
  completed: "全部完成",
};

export default function AdminResetCard({ session, onSessionExpired }: {
  session: SessionView;
  onSessionExpired: () => void;
}) {
  const [saved] = useState(savedReset);
  const [record, setRecord] = useState(saved.record);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const locked = useRef(false);
  const [confirmed, setConfirmed] = useState(false);
  const confirmation = useRef<HTMLInputElement>(null);
  const [announcement, setAnnouncement] = useState("");
  const operation = record?.operation;
  const succeeded = operation?.status === "succeeded";
  const canStartNext = succeeded && session.demo_round_id === operation.resulting_round_id;

  function save(next: ResetRecord, beforeRequest = false) {
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
      setRecord(next);
      return true;
    } catch {
      if (!beforeRequest) setRecord(next);
      setError(beforeRequest
        ? "无法保存原管理请求，本次没有提交。请恢复本机存储后再继续。"
        : "无法保存最新管理结果，原请求已保留。请保留本页并查询原操作；不要另建重置。");
      return false;
    }
  }

  function failed(error: unknown) {
    setError(apiErrorMessage(error));
    if (error instanceof ApiError && error.status === 401) onSessionExpired();
  }

  async function readPreview() {
    if (locked.current || saved.error || (record?.request && !canStartNext)) return;
    locked.current = true;
    setBusy(true);
    setError("");
    setConfirmed(false);
    const next: ResetRecord = {
      previewRequest: !record?.request && record?.previewRequest
        ? record.previewRequest : { request_id: crypto.randomUUID(), demo_round_id: session.demo_round_id },
    };
    try {
      if (!save(next, true)) return;
      const preview = await post<ResetPreview>("/admin/demo/reset-preview", { ...next.previewRequest });
      save({ ...next, preview });
      setAnnouncement("已读取重置影响，尚未执行重置。请核对后再次确认。");
    } catch (error) {
      failed(error);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }

  async function reset(event?: FormEvent) {
    event?.preventDefault();
    if (locked.current || !record?.preview || succeeded || saved.error) return;
    if (!record.request && !confirmed) {
      setError("请先核对影响并勾选确认，再提交重置。");
      confirmation.current?.focus();
      return;
    }
    locked.current = true;
    setBusy(true);
    setError("");
    const request: ResetRequest = record.request ?? {
      request_id: crypto.randomUUID(), reset_confirmation_id: record.preview.reset_confirmation_id,
    };
    const next: ResetRecord = { ...record, request };
    try {
      // Save the exact write request before it can reach the server.
      if (!save(next, true)) return;
      const operation = await post<ManagementOperation>("/admin/demo/reset", { ...request });
      save({ ...next, operation });
      setAnnouncement(operation.status === "succeeded" ? "重置已全部完成。请重新进入用户页。" : "重置尚未全部完成，已保留原管理操作。");
    } catch (error) {
      failed(error);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }

  async function query() {
    if (locked.current || !record?.operation) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      const operation = await get<ManagementOperation>("/admin/operations/" + encodeURIComponent(record.operation.management_operation_id));
      save({ ...record, operation });
      setAnnouncement("已只读查询原管理操作。" + (operation.status === "succeeded" ? "重置已全部完成。" : "重置尚未全部完成。"));
    } catch (error) {
      failed(error);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }

  function cancelPreview() {
    if (locked.current || record?.request) return;
    try {
      localStorage.removeItem(storageKey);
      setRecord(null);
      setConfirmed(false);
      setError("");
      setAnnouncement("已取消本次预览，没有执行重置。");
    } catch (error) {
      failed(error);
    }
  }

  if (API_MODE === "contract-demo") return (
    <section className="admin-card demo-reset-card" aria-labelledby="reset-title">
      <h2 id="reset-title">演示整体重置</h2>
      <p>整体重置仅在真实 API 模式提供。当前为契约测试响应，没有执行整体重置。</p>
    </section>
  );

  return (
    <section className="admin-card demo-reset-card" aria-labelledby="reset-title" aria-busy={busy}>
      <h2 id="reset-title">演示整体重置</h2>
      <p>先核对实际影响，再确认重置。当前管理员会话轮次：<code>{session.demo_round_id}</code>。</p>
      <p role="status" className="small-help">{announcement}</p>
      {(saved.error || error) && <p className="notice notice-error" role="alert">{saved.error || error}</p>}
      {!saved.error && !record?.preview && !record?.request && (
        <button type="button" className="button button-secondary" disabled={busy} onClick={() => void readPreview()}>
          {record ? "重试读取重置影响" : "查看重置影响"}
        </button>
      )}
      {record?.preview && !record.request && (
        <form onSubmit={(event) => void reset(event)}>
          <p>将重置轮次：<code>{record.preview.demo_round_id}</code></p>
          <ul>{record.preview.effects.map((effect, index) => <li key={index}>{effect}</li>)}</ul>
          <label className="reset-confirmation">
            <input ref={confirmation} type="checkbox" name="confirm-demo-reset" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} required />
            <span>我已核对以上影响，确认重置本轮演示</span>
          </label>
          <div className="button-row">
            <button className="button button-danger-outline" disabled={busy}>确认并重置本轮演示</button>
            <button type="button" className="button button-secondary" disabled={busy} onClick={cancelPreview}>暂不重置</button>
          </div>
        </form>
      )}
      {record?.request && (
        <>
          <p>原重置请求：<code>{record.request.request_id}</code></p>
          {operation ? (
            <>
              <p>管理编号：<code>{operation.management_operation_id}</code></p>
              <p>最近一次服务端结果：<strong>{succeeded ? "重置已全部完成" : operation.status === "failed" ? "重置未完成" : "重置进行中，尚未完成"}</strong></p>
              <p>阶段：{phases[operation.phase] ?? operation.phase}；原轮次：<code>{operation.source_round_id}</code></p>
              {operation.error && <p className="notice notice-warning">{operation.error.reason}（{operation.error.code}）</p>}
              {succeeded && (
                <p className="notice notice-success">新轮次：<code>{operation.resulting_round_id ?? "服务端未返回"}</code>。请重新进入用户页，旧会话和旧按钮已失效。</p>
              )}
            </>
          ) : <p className="notice notice-warning">本次重置是否受理尚未核实。已保留原请求，只能按原请求找回并继续，不会创建第二次重置。</p>}
          <div className="button-row">
            {operation && <button type="button" className="button button-secondary" disabled={busy} onClick={() => void query()}>只读查询重置进度</button>}
            {!succeeded && <button type="button" className="button button-primary" disabled={busy} onClick={() => void reset()}>{operation ? "继续同一次重置" : "按原请求找回并继续重置"}</button>}
            {succeeded && <a className="button button-secondary" href={userPageUrl()}>重新进入用户页</a>}
            {canStartNext && <button type="button" className="button button-secondary" disabled={busy} onClick={() => void readPreview()}>查看当前轮次的重置影响</button>}
          </div>
          <p className="small-help">刷新页面不会继续执行重置。{succeeded ? "再次重置前，请刷新本页并重新建立当前轮次的管理员会话。" : "查询只读取状态；继续会沿原请求执行剩余步骤。"}</p>
        </>
      )}
    </section>
  );
}
