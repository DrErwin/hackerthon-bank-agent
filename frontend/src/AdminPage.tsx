import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { API_MODE, userPageUrl, apiErrorMessage, get, post, ApiError } from "./api";
import { getPageItems } from "./pagination";
import type { AuditEventDetail, AuditEventSummary, SessionView, VerificationResponse } from "./contracts";
import AdminResetCard from "./AdminResetCard";

function requestId(): string {
  return crypto.randomUUID();
}

function AdminBanner() {
  if (API_MODE !== "contract-demo") return null;
  return (
    <div className="demo-ribbon" role="status">
      <strong>契约测试响应</strong>
      <span>管理员入口只改变本机测试数据，不代表真实管理授权。</span>
    </div>
  );
}

export default function AdminPage() {
  const params = new URLSearchParams(window.location.search);
  const [session, setSession] = useState<SessionView | null>(null);
  const [checking, setChecking] = useState(true);
  const [adminKey, setAdminKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [keyError, setKeyError] = useState("");
  const [taskId, setTaskId] = useState(params.get("task_id") ?? "");
  const [challengeId, setChallengeId] = useState(params.get("challenge_id") ?? "");
  const [demoRoundId, setDemoRoundId] = useState(params.get("demo_round_id") ?? "");
  const [timeline, setTimeline] = useState<AuditEventSummary[]>([]);
  const [timelineError, setTimelineError] = useState("");
  const [detail, setDetail] = useState<AuditEventDetail | null>(null);
  const [faceMessage, setFaceMessage] = useState("");
  const [faceBusy, setFaceBusy] = useState(false);
  const [faceResult, setFaceResult] = useState<"passed" | "failed" | null>(null);
  const pendingFaceRequests = useRef(new Map<string, { request_id: string; submission_id: string }>());

  useEffect(() => {
    let cancelled = false;
    void get<SessionView>("/session")
      .then((current) => {
        if (!cancelled) setSession(current);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (!(error instanceof ApiError && error.status === 401)) setKeyError(apiErrorMessage(error));
      })
      .finally(() => { if (!cancelled) setChecking(false); });
    return () => { cancelled = true; };
  }, []);

  async function enterAdmin(event: FormEvent) {
    event.preventDefault();
    if (!adminKey) return;
    const submittedKey = adminKey;
    setAdminKey("");
    setBusy(true);
    setKeyError("");
    try {
      const current = await post<SessionView>("/session/enter", { request_id: requestId() }, { "X-Demo-Admin-Key": submittedKey });
      if (current.role !== "admin") {
        setKeyError("服务端没有授予管理员会话。普通用户会话不能查看管理员时间线。");
        return;
      }
      setSession(current);
    } catch (error) {
      setKeyError(apiErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function loadTimeline(event?: FormEvent) {
    event?.preventDefault();
    if (!taskId.trim()) {
      setTimelineError("请输入任务编号。");
      return;
    }
    setTimelineError("");
    setDetail(null);
    try {
      const query = new URLSearchParams({ task_id: taskId.trim() });
      if (demoRoundId.trim()) query.set("demo_round_id", demoRoundId.trim());
      const items = await getPageItems<AuditEventSummary>("/admin/audit/events?" + query.toString());
      setTimeline(items);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setSession(null);
      else setTimelineError(apiErrorMessage(error));
    }
  }

  async function loadEvent(eventId: string) {
    setTimelineError("");
    try {
      const result = await get<AuditEventDetail>("/admin/audit/events/" + encodeURIComponent(eventId));
      setDetail(result);
    } catch (error) {
      setTimelineError(apiErrorMessage(error));
    }
  }

  async function answerFace(result: "passed" | "failed") {
    if (!challengeId.trim() || !demoRoundId.trim() || !taskId.trim()) {
      setFaceMessage("请从等待模拟人脸的任务卡进入，或填写任务、验证和轮次编号。");
      return;
    }
    setFaceBusy(true);
    setFaceMessage("");
    const key = challengeId.trim() + ":" + result;
    const ids = pendingFaceRequests.current.get(key) ?? { request_id: requestId(), submission_id: requestId() };
    pendingFaceRequests.current.set(key, ids);
    try {
      const answer = await post<VerificationResponse>(
        "/admin/verifications/" + encodeURIComponent(challengeId.trim()) + "/face-result",
        {
          ...ids,
          demo_round_id: demoRoundId.trim(),
          result,
        },
      );
      pendingFaceRequests.current.delete(key);
      setFaceResult(result);
      setFaceMessage("管理员结果已提交。用户页面将显示当前任务快照；银行结果以服务端返回为准。");
      if (answer.task.data?.operation?.operation_status === "succeeded") {
        setFaceMessage(API_MODE === "contract-demo"
          ? "契约测试响应模拟了银行成功结果。请在普通页面核对明确标记为测试响应的任务和回执。"
          : "模拟人脸通过；服务端报告银行操作成功。请在普通页面核对任务和银行回执。");
      } else if (answer.kind === "rejected") {
        setFaceMessage("模拟验证未通过。没有因本页面的按钮直接提交银行操作。");
      }
      if (taskId.trim()) await loadTimeline();
    } catch (error) {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429) {
        pendingFaceRequests.current.delete(key);
      }
      setFaceMessage(apiErrorMessage(error));
    } finally {
      setFaceBusy(false);
    }
  }

  if (checking) {
    return <main className="admin-page"><a className="skip-link" href="#main-content">跳到主要内容</a><AdminBanner /><p className="loading-copy" id="main-content" tabIndex={-1}>正在检查独立管理员会话…</p></main>;
  }

  if (!session || session.role !== "admin") {
    return (
      <main className="admin-page">
        <a className="skip-link" href="#main-content">跳到主要内容</a>
        <AdminBanner />
        <header className="admin-header">
          <div className="brand-mark" aria-hidden="true">管</div>
          <div><p className="eyebrow">独立会话</p><h1>管理员演示入口</h1></div>
          <a className="button button-secondary" href={userPageUrl()}>返回普通页面</a>
        </header>
        {session?.role === "user" ? (
          <section className="admin-gate-card" id="main-content" tabIndex={-1}>
            <h2>当前会话没有管理权限</h2>
            <p>普通用户会话不能查看时间线或回答模拟人脸。请使用服务端配置的管理员凭据建立独立会话。</p>
            <button className="button button-secondary" onClick={() => setSession(null)}>切换到管理员登录</button>
          </section>
        ) : (
          <section className="admin-gate-card" id="main-content" tabIndex={-1}>
            <h2>验证管理员身份</h2>
            <p>{API_MODE === "contract-demo" ? "测试模式会接受任意非空口令，并且只修改本机测试数据。" : "管理密钥只在本次请求中使用，不会放进普通页面或浏览器持久存储。"}</p>
            <form className="stack-form" onSubmit={(event) => void enterAdmin(event)}>
              <label htmlFor="admin-key">{API_MODE === "contract-demo" ? "测试管理员口令" : "管理密钥"}</label>
              <input id="admin-key" name="admin-key" type="password" autoComplete="off" value={adminKey} onChange={(event) => setAdminKey(event.target.value)} required />
              <button className="button button-primary" disabled={busy}>{busy ? "验证中…" : "建立管理员会话"}</button>
            </form>
            {keyError && <p className="notice notice-error" role="alert">{keyError}</p>}
          </section>
        )}
      </main>
    );
  }

  return (
    <main className="admin-page">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <AdminBanner />
      <header className="admin-header">
        <div className="brand-mark brand-mark-admin" aria-hidden="true">管</div>
        <div><p className="eyebrow">审计、模拟核验与演示管理</p><h1>管理员演示入口</h1></div>
        <div className="admin-header-actions">
          <span className="identity-pill"><span className="online-dot" />{session.user_display}</span>
          <a className="button button-secondary" href={userPageUrl()}>返回普通页面</a>
        </div>
      </header>

      <div className="admin-content" id="main-content" tabIndex={-1}>
        <AdminResetCard session={session} onSessionExpired={() => setSession(null)} />
        <section className="admin-card face-admin-card">
          <div className="task-card-heading">
            <div><p className="eyebrow">仅处理当前模拟挑战</p><h2>模拟人脸核验</h2></div>
            <span className="admin-only-badge">管理员</span>
          </div>
          <p>本入口只回答服务端已经发起的模拟人脸等待。通过或失败由服务器校验当前轮次、挑战状态和管理员权限。</p>
          <div className="admin-reference-fields">
            <label>任务编号<input name="task-id" value={taskId} onChange={(event) => setTaskId(event.target.value)} placeholder="从普通用户任务卡带入" /></label>
            <label>验证编号<input name="challenge-id" value={challengeId} onChange={(event) => setChallengeId(event.target.value)} placeholder="从普通用户等待卡带入" /></label>
            <label>演示轮次<input name="demo-round-id" value={demoRoundId} onChange={(event) => setDemoRoundId(event.target.value)} placeholder="由服务端返回" /></label>
          </div>
          <div className="button-row">
            <button className="button button-primary" disabled={faceBusy || faceResult === "passed"} onClick={() => void answerFace("passed")}>
              {faceBusy ? "提交中…" : "模拟通过"}
            </button>
            <button className="button button-danger-outline" disabled={faceBusy || faceResult === "failed"} onClick={() => void answerFace("failed")}>模拟未通过</button>
          </div>
          {faceMessage && <p className={faceResult ? "notice notice-success" : "notice notice-warning"} role="status">{faceMessage}</p>}
          <p className="small-help">不做真实人脸识别。重复或过期挑战会由后端拒绝。</p>
        </section>

        <section className="admin-card">
          <div className="task-card-heading"><div><p className="eyebrow">脱敏、只读</p><h2>运行时间线</h2></div><span className="admin-only-badge">F33 / F34</span></div>
          <form className="admin-search-form" onSubmit={(event) => void loadTimeline(event)}>
            <label htmlFor="timeline-task">按任务编号查看</label>
            <div className="inline-form-row">
              <input id="timeline-task" name="timeline-task-id" value={taskId} onChange={(event) => setTaskId(event.target.value)} placeholder="任务编号" required />
              <button className="button button-primary">读取时间线</button>
            </div>
          </form>
          {timelineError && <p className="notice notice-error" role="alert">{timelineError}</p>}
          {timeline.length === 0 ? <p className="muted-copy">选择一个任务后，服务端返回的脱敏记录会显示在这里。</p> : (
            <ol className="timeline-list">
              {timeline.map((event) => (
                <li key={event.event_id}>
                  <span className="timeline-marker" aria-hidden="true" />
                  <button className="timeline-event" onClick={() => void loadEvent(event.event_id)}>
                    <strong>{event.event_type}</strong>
                    <span>{event.module} · {event.outcome}</span>
                    <time dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleString("zh-CN")}</time>
                  </button>
                </li>
              ))}
            </ol>
          )}
          {detail && (
            <section className="audit-detail">
              <div className="task-card-heading"><div><p className="eyebrow">脱敏证据详情</p><h3>{detail.event_type}</h3></div><button className="icon-button" onClick={() => setDetail(null)} aria-label="关闭详情">×</button></div>
              <p>证据状态：{detail.evidence_status}{detail.missing_reason ? " · " + detail.missing_reason : ""}</p>
              <pre>{JSON.stringify({ payload: detail.payload, evidence: detail.evidence }, null, 2)}</pre>
            </section>
          )}
        </section>
      </div>
    </main>
  );
}
