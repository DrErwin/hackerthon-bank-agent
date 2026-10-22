import { useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import type { MessageView } from "../../contracts";
import type { DataOrigin } from "../types";
import { clockTime, originLabel } from "../format";

export function TopBar({ title, connected, expired, origin, userDisplay }: {
  title: string;
  connected: boolean;
  expired: boolean;
  origin: DataOrigin;
  userDisplay: string | null;
}) {
  const state = expired ? { cls: "sh-conn-off", text: "登录已过期" } : connected ? { cls: "sh-conn-on", text: "已连接" } : { cls: "sh-conn-wait", text: "正在连接" };
  const demo = originLabel(origin);
  return (
    <>
      <header className="sh-topbar">
        <div className="sh-brand">
          <span className="sh-brand-mark" aria-hidden="true">银</span>
          <div>
            <h1>{title}</h1>
            {userDisplay && <p>{userDisplay}</p>}
          </div>
        </div>
        <span className={"sh-conn " + state.cls} role="status">
          <span className="sh-conn-dot" aria-hidden="true" />
          {state.text}
        </span>
      </header>
      {demo && (
        <div className="sh-ribbon" role="note">
          <strong>{demo}</strong>
          <span>页面里的回复、验证和结果都是演示数据，不会调用真实银行。</span>
        </div>
      )}
    </>
  );
}

export function MessageBubble({ message, cardSummary }: { message: MessageView; cardSummary?: string }) {
  return (
    <article className={"sh-msg sh-msg-" + message.role}>
      <span className="sr-only">{message.role === "user" ? "您说：" : "助手说："}</span>
      {cardSummary ? <div className="sh-bubble"><p>{cardSummary}</p>
        <details><summary>查看完整说明</summary><p>{message.text}</p></details>
      </div> : <p className="sh-bubble">{message.text}</p>}
      <time className="sh-time" dateTime={message.created_at}>{clockTime(message.created_at)}</time>
    </article>
  );
}

export function TypingBubble() {
  return (
    <div className="sh-msg sh-msg-assistant" role="status">
      <p className="sh-bubble sh-typing"><span className="sr-only">助手正在回复</span><i /><i /><i /></p>
    </div>
  );
}

export function Composer({ disabled, sending, pendingText, voiceDemoText, onSend }: {
  disabled: boolean;
  sending: boolean;
  pendingText: string | null;
  voiceDemoText?: string;
  onSend: (text: string) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState("");
  const [listening, setListening] = useState(false);
  const [voiceNote, setVoiceNote] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const value = pendingText ?? draft;
  const canSend = !disabled && !sending && value.trim().length > 0;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSend) return;
    const cleared = await onSend(value);
    if (cleared) {
      setDraft("");
      setVoiceNote("");
    }
  }

  function startListening() {
    if (disabled || pendingText) return;
    setListening(true);
    setVoiceNote("");
  }

  function stopListening() {
    if (!listening) return;
    setListening(false);
    if (voiceDemoText) {
      setDraft(voiceDemoText);
      setVoiceNote("已填入固定语音示例，没有录音或识别声音。请修改后再发送。");
      inputRef.current?.focus();
    } else {
      setVoiceNote("本页尚未接入真实语音识别，请打字或填写卡片。");
    }
  }

  function onMicKey(event: KeyboardEvent<HTMLButtonElement>, down: boolean) {
    if (event.key !== " " && event.key !== "Enter") return;
    event.preventDefault();
    if (down && !event.repeat) startListening();
    if (!down) stopListening();
  }

  return (
    <div className="sh-composer-wrap">
      {listening && (
        <div className="sh-listening" role="status">
          <span className="sh-wave" aria-hidden="true"><i /><i /><i /><i /><i /></span>
          语音交互演示：松开后填入固定示例，不会录音
        </div>
      )}
      <form className="sh-composer" onSubmit={(event) => void submit(event)}>
        <button
          type="button"
          className={"sh-mic" + (listening ? " sh-mic-on" : "")}
          aria-label="语音示例（固定文字，不录音）"
          aria-pressed={listening}
          disabled={disabled || Boolean(pendingText)}
          onPointerDown={(event) => { event.preventDefault(); startListening(); }}
          onPointerUp={stopListening}
          onPointerLeave={stopListening}
          onPointerCancel={stopListening}
          onKeyDown={(event) => onMicKey(event, true)}
          onKeyUp={(event) => onMicKey(event, false)}
        >
          <svg className="sh-mic-icon" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="9" y="3" width="6" height="11" rx="3" />
            <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7" fill="none" />
          </svg>
        </button>
        <label className="sr-only" htmlFor="sh-input">输入您想办的事</label>
        <input
          ref={inputRef}
          id="sh-input"
          className="sh-input"
          value={value}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="说说您想办什么…"
          autoComplete="off"
          disabled={disabled || Boolean(pendingText)}
        />
        <button className="sh-send" disabled={!canSend}>
          {sending ? "发送中" : pendingText ? "重试" : "发送"}
        </button>
      </form>
      <p className="sh-composer-hint" aria-live="polite">
        {pendingText && !sending ? "上一条消息还没确认发出。点「重试」即可，不会重复办理。" : voiceNote || "验证码只填专用框。麦克风是文字演示，不录音。"}
      </p>
    </div>
  );
}

export function ExpiredBanner({ onReenter }: { onReenter: () => void }) {
  return (
    <div className="sh-expired" role="alert">
      <div>
        <strong>演示登录已过期</strong>
        <p>旧的按钮已经不能再点。重新进入后会先查看原任务，不会重复提交。</p>
      </div>
      <button type="button" className="sh-btn sh-btn-primary" onClick={onReenter}>点这里重新进入</button>
    </div>
  );
}

export function SafetyRail() {
  return (
    <aside className="sh-safety-help" aria-label="办理须知">
      <details><summary>安心办理：转钱前，先核对再确认</summary>
      <ol>
        <li><strong>动钱必须点按钮确认。</strong>在聊天里说「确认」不算数。</li>
        <li><strong>验证码只填在专用框里。</strong>不要告诉任何人，也不要发到聊天里。</li>
        <li><strong>刷新不会重复办理。</strong>页面会先请您查看原任务。</li>
        <li><strong>结果以银行返回为准。</strong>暂时查不到时，会显示「结果待核实」。</li>
      </ol>
      </details>
    </aside>
  );
}
