import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { DemoCodeView, InteractionOption, VerificationView } from "../../contracts";
import { EDIT_OPTION_NOTE } from "../copy";
import { clockTime } from "../format";
import { Card, FieldList, ReadOnlyStamp, StatusBadge } from "./Primitives";
import { Button } from "@/components/ui/button";
import { ScanFace } from "lucide-react";

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
  if (view.face_result === "pending") return view.face_started_at ? "等工作人员处理" : "尚未开始";
  return { passed: "已通过", failed: "未通过", expired: "已超时", cancelled: "已取消", not_required: "不需要" }[view.face_result];
}

function CodeBoxes({ value, onChange, disabled, inputId, errorId }: { value: string; onChange: (value: string) => void; disabled: boolean; inputId: string; errorId?: string }) {
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
        aria-invalid={Boolean(errorId)}
        aria-describedby={errorId}
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

export function VerificationCard({ view, active, canVerify, busy, adminHref, adminLabel = "演示用：管理员入口", options, onSelectOption, onSubmitCode, onResend, onStartFace, onShowDemoCode, canCancel = false, id }: {
  view: VerificationView;
  active: boolean;
  canVerify: boolean;
  busy: boolean;
  adminHref: string | null;
  adminLabel?: string;
  // Options published by the backend on this card (the birthday controlled edit).
  // They are answered by option id through F10, never by matching their label.
  options?: InteractionOption[];
  onSelectOption?: (optionId: string, label: string) => void;
  onSubmitCode: (code: string) => Promise<string | null>;
  onResend: () => void;
  onStartFace: () => void;
  onShowDemoCode: () => Promise<DemoCodeView | null>;
  // Whether this task still shows its own "取消这次办理" button.
  canCancel?: boolean;
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
      title={live ? needsCode && needsFace ? "请完成两项身份验证" : "请验证身份" : "安全验证记录"}
      labelledBy={id}
      readOnly={!live}
      highlight={live}
      className="sh-verification"
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
                  <span>演示验证码</span>
                  {demoCode ? <strong>{demoCode.code}</strong> : (
                    <button type="button" className="sh-link-btn" onClick={() => void showDemoCode()}>点这里查看</button>
                  )}
                  {demoCode && <small>30 秒后自动隐藏，{clockTime(demoCode.expires_at)} 前有效</small>}
                </div>
                <label className="sh-label" htmlFor={id + "-code"}>请输入 6 位验证码</label>
                <CodeBoxes value={code} onChange={(value) => { setCode(value); setCodeMessage(""); }} disabled={busy} inputId={id + "-code"} errorId={codeMessage ? id + "-error" : undefined} />
                {codeMessage && <p id={id + "-error"} className="sh-inline-error" role="alert">{codeMessage}</p>}
                <Button disabled={busy || code.length !== 6}>{busy ? "正在验证…" : "提交验证码"}</Button>
                <Button type="button" variant="outline" disabled={busy} onClick={() => { setCode(""); setCodeMessage(""); setDemoCode(null); onResend(); }}>重新获取验证码</Button>
                <p className="sh-hint">验证码请填在上方专用框，{clockTime(view.code_expires_at)} 前有效。</p>
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
              <Button type="button" disabled={busy} onClick={onStartFace}>
                <ScanFace aria-hidden="true" />
                {busy ? "正在开始…" : "开始模拟人脸验证"}
              </Button>
            )}
            {live && view.face_started_at && view.face_result === "pending" && (
              <div className="sh-face-wait" role="status">
                <ScanFace className="sh-face-mark" aria-hidden="true" />
                <p className="sh-lead">请稍等，工作人员会帮您完成刷脸验证，完成后这里会自动更新。</p>
                <p className="sh-hint">{clockTime(view.face_expires_at)} 前有效。</p>
                {adminHref && (
                  <a className="sh-demo-note sh-admin-link" href={adminHref} target="_blank" rel="noreferrer">{adminLabel}</a>
                )}
              </div>
            )}
          </li>
        )}
      </ol>
      {live && (options ?? []).length > 0 && (
        <>
          <div className="sh-actions">
            {(options ?? []).map((option) => (
              <button key={option.id} type="button" className="sh-btn sh-btn-secondary" disabled={busy}
                onClick={() => onSelectOption?.(option.id, option.label)}>{option.label}</button>
            ))}
          </div>
          <p className="sh-hint">{EDIT_OPTION_NOTE}</p>
        </>
      )}
      {!live && <p className="sh-readonly-line">{view.challenge_status === "expired"
        ? "验证超时了，钱没有动。" + (canCancel ? "请点「取消这次办理」，再重新办一次。" : "")
        : "验证记录已保存，供您回看。"}</p>}
    </Card>
  );
}
