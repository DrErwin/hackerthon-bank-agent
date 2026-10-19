import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { DemoCodeView, VerificationView } from "../../contracts";
import { clockTime } from "../format";
import { Card, FieldList, ReadOnlyStamp, StatusBadge } from "./Primitives";

const CHALLENGE_TEXT: Record<VerificationView["challenge_status"], string> = {
  pending: "验证已暂停",
  passed: "验证已通过",
  failed: "验证未通过",
  expired: "验证已超时",
  superseded: "已被新验证替代",
  cancelled: "验证已取消",
};

const CODE_TEXT: Record<VerificationView["code_result"], string> = {
  pending: "等待输入",
  passed: "已通过",
  failed: "未通过",
  expired: "已超时",
  cancelled: "已取消",
};

function faceText(view: VerificationView): string {
  if (view.face_result === "pending") return view.face_started_at ? "等待管理员作答" : "尚未开始";
  return { passed: "已通过", failed: "未通过", expired: "已超时", cancelled: "已取消", not_required: "不需要" }[view.face_result];
}

function CodeBoxes({ value, onChange, disabled, inputId }: { value: string; onChange: (value: string) => void; disabled: boolean; inputId: string }) {
  return (
    <div className="sh-code">
      <input
        id={inputId}
        className="sh-code-input"
        name="verification-code"
        inputMode="numeric"
        autoComplete="one-time-code"
        spellCheck={false}
        maxLength={6}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, "").slice(0, 6))}
      />
      <div className="sh-code-boxes" aria-hidden="true">
        {Array.from({ length: 6 }, (_, index) => (
          <span key={index} className={"sh-code-box" + (index === value.length ? " sh-code-box-current" : "")}>{value[index] ?? ""}</span>
        ))}
      </div>
    </div>
  );
}

export function VerificationCard({ view, active, canVerify, busy, adminHref, adminLabel = "演示用：在新窗口打开管理员演示入口", onSubmitCode, onResend, onStartFace, onShowDemoCode, id }: {
  view: VerificationView;
  active: boolean;
  canVerify: boolean;
  busy: boolean;
  adminHref: string | null;
  adminLabel?: string;
  onSubmitCode: (code: string) => Promise<string | null>;
  onResend: () => void;
  onStartFace: () => void;
  onShowDemoCode: () => Promise<DemoCodeView | null>;
  id: string;
}) {
  const [code, setCode] = useState("");
  const [codeMessage, setCodeMessage] = useState("");
  const [demoCode, setDemoCode] = useState<DemoCodeView | null>(null);
  const submitting = useRef(false);
  const live = active && view.challenge_status === "pending";
  const needsCode = view.required_methods.includes("code");
  const needsFace = view.required_methods.includes("mock_face");
  const codeDone = !needsCode || view.code_result === "passed";

  useEffect(() => {
    if (!demoCode) return;
    const timer = window.setTimeout(() => setDemoCode(null), 30_000);
    return () => window.clearTimeout(timer);
  }, [demoCode]);

  useEffect(() => {
    if (!live) {
      setCode("");
      setDemoCode(null);
    }
  }, [live]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting.current || code.length !== 6) return;
    submitting.current = true;
    const submitted = code;
    setCode("");
    setCodeMessage("");
    try {
      const message = await onSubmitCode(submitted);
      if (message) setCodeMessage(message);
      setDemoCode(null);
    } finally {
      submitting.current = false;
    }
  }

  async function showDemoCode() {
    const value = await onShowDemoCode();
    if (value && value.challenge_id === view.challenge_id) setDemoCode(value);
  }

  return (
    <Card
      title={live ? "为了安全，请完成两项验证" : "安全验证记录"}
      labelledBy={id}
      readOnly={!live}
      highlight={live}
      badge={live ? <StatusBadge tone="pending" icon="◆" text="等您验证" /> : <ReadOnlyStamp text={CHALLENGE_TEXT[view.challenge_status]} />}
    >
      {view.summary && live && <FieldList fields={view.summary.display_fields} />}
      <ol className="sh-steps">
        {needsCode && (
          <li className={"sh-step" + (view.code_result === "passed" ? " sh-step-done" : "")}>
            <div className="sh-step-head">
              <span className="sh-step-no" aria-hidden="true">1</span>
              <strong>验证码</strong>
              <span className="sh-step-state">{CODE_TEXT[view.code_result]}</span>
            </div>
            {live && canVerify && view.code_result === "pending" && (
              <form className="sh-code-form" onSubmit={(event) => void submit(event)}>
                <div className="sh-demo-code" aria-live="polite">
                  <span>模拟验证码（演示专用提示区）</span>
                  {demoCode ? <strong>{demoCode.code}</strong> : (
                    <button type="button" className="sh-link-btn" onClick={() => void showDemoCode()}>点这里查看</button>
                  )}
                  {demoCode && <small>30 秒后自动隐藏，{clockTime(demoCode.expires_at)} 前有效</small>}
                </div>
                <label className="sh-label" htmlFor={id + "-code"}>请输入 6 位验证码</label>
                <CodeBoxes value={code} onChange={setCode} disabled={busy} inputId={id + "-code"} />
                {codeMessage && <p className="sh-inline-error" role="alert">{codeMessage}</p>}
                <button className="sh-btn sh-btn-primary" disabled={busy || code.length !== 6}>{busy ? "正在提交…" : "提交验证码"}</button>
                <button type="button" className="sh-btn sh-btn-secondary" disabled={busy} onClick={onResend}>重新获取验证码</button>
                <p className="sh-hint">验证码只填在这里，不要发到聊天里。请在 {clockTime(view.code_expires_at)} 前完成。</p>
              </form>
            )}
          </li>
        )}
        {needsFace && (
          <li className={"sh-step" + (view.face_result === "passed" ? " sh-step-done" : "")}>
            <div className="sh-step-head">
              <span className="sh-step-no" aria-hidden="true">{needsCode ? 2 : 1}</span>
              <strong>模拟人脸验证</strong>
              <span className="sh-step-state">{faceText(view)}</span>
            </div>
            {live && !codeDone && <p className="sh-hint">请先完成验证码。</p>}
            {live && canVerify && codeDone && !view.face_started_at && (
              <button type="button" className="sh-btn sh-btn-primary" disabled={busy} onClick={onStartFace}>
                {busy ? "正在开始…" : "开始模拟人脸验证"}
              </button>
            )}
            {live && view.face_started_at && view.face_result === "pending" && (
              <div className="sh-face-wait" role="status">
                <span className="sh-face-mark" aria-hidden="true" />
                <p className="sh-lead">正在等待管理员在独立演示端作答。</p>
                <p className="sh-hint">本页面没有「通过」按钮，结果以后台返回为准。不会开启摄像头，也不采集生物信息。请在 {clockTime(view.face_expires_at)} 前完成。</p>
                {adminHref && (
                  <a className="sh-link-btn" href={adminHref} target="_blank" rel="noreferrer">{adminLabel}</a>
                )}
              </div>
            )}
          </li>
        )}
      </ol>
      {!live && <p className="sh-readonly-line">这项验证已转为只读，不会再次提交。</p>}
    </Card>
  );
}
