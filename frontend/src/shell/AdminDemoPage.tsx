import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api";
import type { SessionView } from "../contracts";
import { clockTime, newRequestId } from "./format";
import { FieldList, Notice, OriginTag, StatusBadge } from "./components/Primitives";
import type { PendingFaceChallenge, StubAdminExtras } from "./stub/demoBackend";
import type { AdminDemoSource } from "./types";

export function AdminDemoPage({ admin, stubExtras }: { admin: AdminDemoSource; stubExtras: StubAdminExtras | null }) {
  const params = new URLSearchParams(window.location.search);
  const linked: PendingFaceChallenge | null = params.get("challenge_id")
    ? { challenge_id: params.get("challenge_id")!, task_id: params.get("task_id") ?? "", demo_round_id: params.get("demo_round_id") ?? "", display_fields: [], face_expires_at: null }
    : null;
  const [session, setSession] = useState<SessionView | null>(null);
  const [checking, setChecking] = useState(true);
  const [pending, setPending] = useState<PendingFaceChallenge[]>([]);
  const [message, setMessage] = useState<{ tone: "info" | "warning" | "danger"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [resultUnknown, setResultUnknown] = useState(false);
  const requestIds = useRef(new Map<string, { request_id: string; submission_id: string }>());

  const refresh = useCallback(() => {
    if (!stubExtras) return;
    setPending(stubExtras.listPendingFaceChallenges());
    setResultUnknown(stubExtras.getFaults().resultUnknown);
  }, [stubExtras]);

  useEffect(() => {
    void admin.getAdminSession().then(setSession).catch(() => setSession(null)).finally(() => setChecking(false));
  }, [admin]);

  useEffect(() => {
    if (!session) return;
    refresh();
    const timer = window.setInterval(refresh, 1000);
    return () => window.clearInterval(timer);
  }, [refresh, session]);

  async function enter() {
    setBusy(true);
    try {
      setSession(await admin.enterAdmin({ request_id: newRequestId() }));
    } catch (error) {
      setMessage({ tone: "danger", text: error instanceof ApiError ? error.message : "没有进入管理员演示端。" });
    } finally {
      setBusy(false);
    }
  }

  async function answer(challenge: PendingFaceChallenge, result: "passed" | "failed") {
    if (busy) return;
    const key = challenge.challenge_id + ":" + result;
    const ids = requestIds.current.get(key) ?? { request_id: newRequestId(), submission_id: newRequestId() };
    requestIds.current.set(key, ids);
    setBusy(true);
    setMessage(null);
    try {
      await admin.answerFace(challenge.challenge_id, { ...ids, demo_round_id: challenge.demo_round_id, result });
      requestIds.current.delete(key);
      setMessage({
        tone: "info",
        text: result === "passed"
          ? "已提交「模拟成功」。用户页会读取验证结果，本页面不会直接执行转账。"
          : "已提交「模拟失败」。用户页会显示办理终止，没有提交给银行。",
      });
    } catch (error) {
      if (error instanceof ApiError && error.status < 500 && error.status !== 0) requestIds.current.delete(key);
      setMessage({ tone: "warning", text: error instanceof ApiError ? error.message : "提交没有完成，可以再点一次。" });
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function expireUser() {
    if (!session) return;
    try {
      await admin.expireUserSession({ request_id: newRequestId(), demo_round_id: session.demo_round_id });
      setMessage({ tone: "info", text: "用户演示登录已过期。用户页的旧按钮会失效，需要重新进入。" });
    } catch (error) {
      setMessage({ tone: "warning", text: error instanceof ApiError ? error.message : "操作没有完成。" });
    }
  }

  const challenges = [...pending];
  if (linked && !challenges.some((item) => item.challenge_id === linked.challenge_id) && !stubExtras) challenges.push(linked);

  return (
    <div className="sh-root sh-admin">
      <header className="sh-topbar sh-topbar-admin">
        <div className="sh-brand">
          <span className="sh-brand-mark sh-brand-admin" aria-hidden="true">管</span>
          <div><h1>管理员演示入口</h1><p>独立演示端，与用户页分开</p></div>
        </div>
        <div className="sh-topbar-side"><OriginTag origin={admin.origin} /></div>
      </header>
      <main className="sh-admin-main">
        <Notice tone="warning" title="这里只用于演示">
          <p>本页只能回答「已经开始等待」的模拟人脸验证，不能执行转账，也不能替用户确认。正式环境中管理员权限由后端逐次校验{admin.origin === "stub" ? "；当前 stub 模式不校验真实权限" : ""}。</p>
        </Notice>
        {checking ? <p className="sh-hint">正在检查管理员演示会话…</p> : !session ? (
          <section className="sh-card">
            <header className="sh-card-head"><h3>进入管理员演示端</h3></header>
            <p className="sh-hint">进入后会建立一个与用户页分开的演示管理员会话。</p>
            <button type="button" className="sh-btn sh-btn-primary" disabled={busy} onClick={() => void enter()}>进入管理员演示端</button>
          </section>
        ) : (
          <>
            <section className="sh-card" aria-labelledby="face-title">
              <header className="sh-card-head"><h3 id="face-title">等待作答的模拟人脸验证</h3><StatusBadge tone="neutral" icon="◆" text={challenges.length + " 项"} /></header>
              {challenges.length === 0 && <p className="sh-hint">现在没有等待作答的模拟人脸验证。用户在验证卡上点「开始模拟人脸验证」后会出现在这里。</p>}
              {challenges.map((challenge) => (
                <div className="sh-admin-item" key={challenge.challenge_id}>
                  <FieldList fields={challenge.display_fields} emphasize="amount" />
                  {challenge.face_expires_at && <p className="sh-hint">请在 {clockTime(challenge.face_expires_at)} 前作答，超时后用户办理会终止。</p>}
                  <div className="sh-actions">
                    <button type="button" className="sh-btn sh-btn-primary" disabled={busy} onClick={() => void answer(challenge, "passed")}>提交模拟成功</button>
                    <button type="button" className="sh-btn sh-btn-danger" disabled={busy} onClick={() => void answer(challenge, "failed")}>提交模拟失败</button>
                  </div>
                </div>
              ))}
              {message && <Notice tone={message.tone} title={message.tone === "info" ? "已提交" : "没有完成"}>{message.text}</Notice>}
            </section>
            <section className="sh-card" aria-labelledby="ops-title">
              <header className="sh-card-head"><h3 id="ops-title">其他演示操作</h3></header>
              <button type="button" className="sh-btn sh-btn-secondary" onClick={() => void expireUser()}>让用户演示登录立即过期</button>
              {stubExtras && (
                <>
                  <label className="sh-toggle">
                    <input type="checkbox" checked={resultUnknown} onChange={(event) => { stubExtras.setResultUnknownFault(event.target.checked); refresh(); }} />
                    <span>下一笔银行结果设为「待核实」（仅 stub 演示，用于展示查询原操作）</span>
                  </label>
                  <button type="button" className="sh-btn sh-btn-quiet" onClick={() => { stubExtras.resetDemo(); window.location.reload(); }}>清空全部演示数据</button>
                </>
              )}
            </section>
          </>
        )}
        <p className="sh-hint"><a href="/v04">返回用户页</a></p>
      </main>
    </div>
  );
}
