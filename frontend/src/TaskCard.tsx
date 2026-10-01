import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { API_MODE, administratorUrl, apiErrorMessage, get, post, ApiError } from "./api";
import type {
  ConfirmationView,
  DemoCodeView,
  DetailsResponse,
  DisplayField,
  PayeeCandidate,
  TaskView,
  VerificationResponse,
  VerificationView,
} from "./contracts";

interface TaskCardProps {
  task: TaskView;
  onTask: (task: TaskView) => void;
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
  onSessionExpired: () => void;
  onModifyDraft: (text: string) => void;
}

function newId(): string {
  return crypto.randomUUID();
}

function amount(fen: number | null | undefined): string {
  return typeof fen === "number" ? "¥" + (fen / 100).toFixed(2) : "未提供";
}

function displayTime(value: string | null): string {
  return value ? new Date(value).toLocaleString("zh-CN") : "未开始";
}

function statusLabel(task: TaskView): string {
  if (task.status === "running") return "正在处理";
  if (task.status === "waiting_input") return "等待补充信息";
  if (task.status === "waiting_approval") return task.interaction?.kind === "verification" ? "等待专用验证" : "等待正式确认";
  if (task.status === "needs_attention") return "待核实";
  if (task.status === "partially_succeeded") return "部分完成";
  if (task.status === "cancelled") return "已取消";
  if (task.status === "failed") return "处理失败";
  const operation = task.data?.operation;
  if (operation?.operation_status === "succeeded") return "银行返回成功";
  if (operation?.operation_status === "failed") return "银行返回失败";
  if (operation?.operation_status === "processing") return "银行处理中";
  return "任务已结束，银行结果未返回";
}

function statusClass(task: TaskView): string {
  if (task.status === "succeeded" && task.data?.operation?.operation_status === "succeeded") return "state-success";
  if (task.status === "failed" || task.status === "cancelled" || task.data?.operation?.operation_status === "failed") return "state-danger";
  if (task.status === "needs_attention") return "state-warning";
  return "state-pending";
}

function Fields({ fields }: { fields: DisplayField[] }) {
  if (fields.length === 0) return <p className="muted-copy">服务暂未返回可展示字段。</p>;
  return (
    <dl className="field-list">
      {fields.map((field) => (
        <div className="field-row" key={field.name}>
          <dt>{field.label}</dt>
          <dd>{field.value_text}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function TaskCard(props: TaskCardProps) {
  const { task } = props;
  const [confirmation, setConfirmation] = useState<ConfirmationView | null>(null);
  const [verification, setVerification] = useState<VerificationView | null>(null);
  const [recordLoading, setRecordLoading] = useState(false);
  const [recordError, setRecordError] = useState("");
  const [actionError, setActionError] = useState("");
  const [busyKey, setBusyKey] = useState("");
  const [retryKey, setRetryKey] = useState("");
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [confirmingTaskCancel, setConfirmingTaskCancel] = useState(false);
  const [inputText, setInputText] = useState("");
  const [candidates, setCandidates] = useState<PayeeCandidate[]>([]);
  const [detailsMode, setDetailsMode] = useState<"search" | "manual" | null>(null);
  const [searchKind, setSearchKind] = useState("name");
  const [searchValue, setSearchValue] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [accountName, setAccountName] = useState("");
  const [code, setCode] = useState("");
  const [demoCode, setDemoCode] = useState<DemoCodeView | null>(null);
  const [modifying, setModifying] = useState(false);
  const [modifyText, setModifyText] = useState("");
  const pendingMutations = useRef(new Map<string, { path: string; body: Record<string, unknown> }>());

  const recordRef = task.interaction?.record_ref ?? null;
  const interactionKind = task.interaction?.kind ?? null;

  useEffect(() => {
    setConfirmation(null);
    setVerification(null);
    setRecordError("");
    setConfirmingCancel(false);
    if (!recordRef || !interactionKind || (interactionKind !== "confirmation" && interactionKind !== "verification")) return;
    let cancelled = false;
    setRecordLoading(true);
    const path = interactionKind === "confirmation" ? "/confirmations/" : "/verifications/";
    void get<ConfirmationView | VerificationView>(path + encodeURIComponent(recordRef))
      .then((record) => {
        if (cancelled) return;
        if (interactionKind === "confirmation") setConfirmation(record as ConfirmationView);
        else setVerification(record as VerificationView);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) props.onSessionExpired();
        else setRecordError(apiErrorMessage(error));
      })
      .finally(() => {
        if (!cancelled) setRecordLoading(false);
      });
    return () => { cancelled = true; };
  }, [recordRef, interactionKind, task.task_id, props.onSessionExpired]);

  useEffect(() => {
    if (!demoCode) return;
    const timer = window.setTimeout(() => setDemoCode(null), 30_000);
    return () => window.clearTimeout(timer);
  }, [demoCode]);

  async function mutate<T>(key: string, path: string, body: Record<string, unknown>): Promise<T | null> {
    const pending = pendingMutations.current.get(key) ?? {
      path,
      body: { ...body, request_id: newId() },
    };
    pendingMutations.current.set(key, pending);
    setBusyKey(key);
    setRetryKey("");
    setActionError("");
    try {
      const result = await post<T>(pending.path, pending.body);
      pendingMutations.current.delete(key);
      setRetryKey("");
      const resultObject = result as { task?: TaskView; task_id?: string };
      if (resultObject?.task) props.onTask(resultObject.task);
      else if (resultObject?.task_id) props.onTask(result as TaskView);
      await props.onRefresh();
      return result;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) props.onSessionExpired();
      if (error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 429) {
        pendingMutations.current.delete(key);
      }
      const canRetry = pendingMutations.current.has(key);
      setRetryKey(canRetry ? key : "");
      if (!(error instanceof ApiError && error.status === 401)) {
        setActionError(apiErrorMessage(error) + (canRetry ? "可重试时会沿用同一个请求编号。" : ""));
      }
      return null;
    } finally {
      setBusyKey("");
    }
  }

  async function submitInput(selectedOptionId?: string) {
    const interaction = task.interaction;
    if (!interaction || !task.allowed_actions.includes("provide_input")) return;
    const text = inputText.trim();
    if (!selectedOptionId && !text) return;
    const result = await mutate<TaskView>(
      "input:" + task.task_id + ":" + (selectedOptionId ?? "text"),
      "/tasks/" + encodeURIComponent(task.task_id) + "/inputs",
      {
        interaction_id: interaction.interaction_id,
        ...(selectedOptionId ? { selected_option_id: selectedOptionId } : { text }),
      },
    );
    if (result) {
      setInputText("");
      setCandidates([]);
    }
  }

  async function submitDetails(kind: "payee_search" | "payee", fields: Record<string, unknown>) {
    const interaction = task.interaction;
    if (!interaction || !task.allowed_actions.includes("provide_input")) return;
    const result = await mutate<DetailsResponse>(
      "details:" + task.task_id + ":" + kind,
      "/tasks/" + encodeURIComponent(task.task_id) + "/details",
      { interaction_id: interaction.interaction_id, kind, fields },
    );
    if (result) {
      setCandidates(result.candidates ?? []);
      setSearchValue("");
      setAccountNumber("");
      setAccountName("");
      setDetailsMode(null);
    }
  }

  async function submitCode(event: FormEvent) {
    event.preventDefault();
    if (!verification || !task.allowed_actions.includes("verify")) return;
    const submittedCode = code;
    if (!submittedCode.trim()) return;
    setCode("");
    setActionError("");
    try {
      const result = await post<VerificationResponse>(
        "/verifications/" + encodeURIComponent(verification.challenge_id) + "/code",
        { request_id: newId(), submission_id: newId(), code: submittedCode },
      );
      setVerification(result.verification);
      props.onTask(result.task);
      if (result.error) setActionError(result.error.reason);
      await props.onRefresh();
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) props.onSessionExpired();
      else {
        setActionError("验证码提交结果尚未确认，正在查询原任务。验证码不会自动重传。");
        try {
          const current = await get<VerificationView>("/verifications/" + encodeURIComponent(verification.challenge_id));
          setVerification(current);
          const currentTask = await get<TaskView>("/tasks/" + encodeURIComponent(task.task_id));
          props.onTask(currentTask);
        } catch {
          // Keep the explicit unknown-result notice. A later refresh reads the same task.
        }
      }
    }
  }

  async function showDemoCode() {
    if (!verification) return;
    try {
      const value = await get<DemoCodeView>("/verifications/" + encodeURIComponent(verification.challenge_id) + "/demo-code");
      setDemoCode(value);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) props.onSessionExpired();
      else setActionError(apiErrorMessage(error));
    }
  }

  async function startFace() {
    if (!verification || !task.allowed_actions.includes("verify")) return;
    const result = await mutate<VerificationView>(
      "face-start:" + verification.challenge_id,
      "/verifications/" + encodeURIComponent(verification.challenge_id) + "/face/start",
      {},
    );
    if (result) setVerification(result);
  }

  async function resendCode() {
    if (!verification || !task.allowed_actions.includes("verify")) return;
    const result = await mutate<VerificationView>(
      "resend-code:" + verification.challenge_id,
      "/verifications/" + encodeURIComponent(verification.challenge_id) + "/resend-code",
      {},
    );
    if (result) {
      setVerification(result);
      setDemoCode(null);
    }
  }

  async function answerConfirmation(choice: "approve" | "cancel") {
    if (!confirmation || !task.interaction) return;
    if (choice === "approve" && !task.allowed_actions.includes("confirm")) return;
    if (choice === "cancel" && !task.allowed_actions.includes("cancel")) return;
    await mutate<TaskView>(
      "confirmation:" + confirmation.confirmation_id + ":" + choice,
      "/confirmations/" + encodeURIComponent(confirmation.confirmation_id) + "/answer",
      { confirmation_version: confirmation.confirmation_version, choice },
    );
    if (choice === "cancel") setConfirmingCancel(false);
  }

  async function submitModification(event: FormEvent) {
    event.preventDefault();
    if (!confirmation || !modifyText.trim()
      || !task.allowed_actions.includes("confirm")
      || !task.allowed_actions.includes("cancel")) return;
    const result = await mutate<TaskView>(
      "confirmation:" + confirmation.confirmation_id + ":modify",
      "/confirmations/" + encodeURIComponent(confirmation.confirmation_id) + "/answer",
      { confirmation_version: confirmation.confirmation_version, choice: "cancel" },
    );
    if (result) {
      props.onTask(result);
      props.onModifyDraft("请将当前转账调整为：" + modifyText.trim() + "。原确认单已取消，请重新核对新的确认单。");
      setModifyText("");
      setModifying(false);
    }
  }

  async function taskAction(command: "cancel" | "resume" | "query-result") {
    const action = command === "query-result" ? "query" : command;
    // The API intentionally clears old-session actions but exposes this single route for explicit recovery.
    const canResumeRecoveredTask = command === "resume" && task.recovery_required;
    if (!task.allowed_actions.includes(action) && !canResumeRecoveredTask) return;
    await mutate<TaskView>(
      "task:" + task.task_id + ":" + command,
      "/tasks/" + encodeURIComponent(task.task_id) + "/" + command,
      {},
    );
  }

  async function selectCandidate(candidateId: string) {
    await submitInput(candidateId);
  }

  const operation = task.data?.operation;
  const receipt = operation?.receipt;
  const activeConfirmation = task.interaction?.kind === "confirmation";
  const activeVerification = task.interaction?.kind === "verification";
  const activeInput = task.interaction?.kind === "input";
  const canConfirm = task.allowed_actions.includes("confirm");
  const canCancel = task.allowed_actions.includes("cancel");
  const canModify = canConfirm && canCancel;
  const canVerify = task.allowed_actions.includes("verify");
  const canProvideInput = task.allowed_actions.includes("provide_input");
  const inputField = task.interaction?.required_fields[0] ?? "";
  const inputLabel = inputField === "amount_fen" ? "金额（元）" : inputField === "payee_hint" ? "收款人" : inputField === "payer_account_id" ? "转出账户" : "补充内容";
  const inputPlaceholder = inputField === "amount_fen" ? "例如 500" : inputField === "payee_hint" ? "输入姓名或备注" : "请输入服务端要求的信息";

  return (
    <section className="task-card" aria-labelledby={"task-title-" + task.task_id}>
      <div className="task-card-heading">
        <div>
          <p className="eyebrow">任务状态</p>
          <h3 id={"task-title-" + task.task_id}>当前办理</h3>
        </div>
        <span className={"state-pill " + statusClass(task)} role="status" aria-live="polite"><span className="status-dot" />{statusLabel(task)}</span>
      </div>
      <p className="task-message">{task.message}</p>
      {task.recovery_required && <p className="notice notice-warning">{task.recovery_reason || "此任务需要恢复核对。"}</p>}
      {task.cancel_requested && <p className="notice notice-warning">已收到停止请求，仍需核对原操作状态。</p>}
      {task.error && <p className="notice notice-error" role="alert">{task.error.reason}</p>}

      {activeInput && task.interaction && (
        <div className="interaction-panel">
          <div className="interaction-heading">
            <span className="step-number">1</span>
            <div><h4>补充信息</h4><p>{task.interaction.prompt}</p></div>
          </div>
          {task.interaction.options.length > 0 && canProvideInput && (
            <div className="choice-list">
              {task.interaction.options.map((option) => (
                <button className="choice-button" key={option.id} disabled={Boolean(busyKey)} onClick={() => void selectCandidate(option.id)}>
                  <span>{option.label}</span><span aria-hidden="true">›</span>
                </button>
              ))}
            </div>
          )}
          {canProvideInput && task.interaction.required_fields.length > 0 && (
            <form className="stack-form" onSubmit={(event) => { event.preventDefault(); void submitInput(); }}>
              <label htmlFor={"input-" + task.task_id}>{inputLabel}</label>
              <div className="inline-form-row">
                <input
                  id={"input-" + task.task_id}
                  name={"task-input-" + inputField}
                  inputMode={task.interaction.required_fields.includes("amount_fen") ? "decimal" : "text"}
                  value={inputText}
                  onChange={(event) => setInputText(event.target.value)}
                  placeholder={inputPlaceholder}
                  autoComplete="off"
                  required
                />
                <button className="button button-primary" disabled={Boolean(busyKey)}>
                  {busyKey.startsWith("input:") ? "提交中…" : "提交补充信息"}
                </button>
              </div>
            </form>
          )}
          {canProvideInput && task.interaction.required_fields.includes("payee_hint") && (
            <div className="details-entry">
              <p>完整账号请在专用资料入口填写，不会加入聊天记录。</p>
              <div className="button-row">
                <button className="button button-secondary" onClick={() => setDetailsMode(detailsMode === "search" ? null : "search")}>
                  查找收款人
                </button>
                <button className="button button-secondary" onClick={() => setDetailsMode(detailsMode === "manual" ? null : "manual")}>
                  填写收款账号
                </button>
              </div>
              {detailsMode === "search" && (
                <form className="stack-form details-form" onSubmit={(event) => {
                  event.preventDefault();
                  void submitDetails("payee_search", { kind: searchKind, value: searchValue });
                }}>
                  <label htmlFor={"search-kind-" + task.task_id}>按哪项查找</label>
                  <select id={"search-kind-" + task.task_id} name="search-kind" value={searchKind} onChange={(event) => setSearchKind(event.target.value)}>
                    <option value="name">姓名</option><option value="phone">手机号</option>
                    <option value="account_number">账号</option><option value="remark">备注</option>
                  </select>
                  <label htmlFor={"search-value-" + task.task_id}>查询内容</label>
                  <div className="inline-form-row">
                    <input id={"search-value-" + task.task_id} name="payee-search-value" value={searchValue} onChange={(event) => setSearchValue(event.target.value)} autoComplete="off" required />
                    <button className="button button-primary" disabled={Boolean(busyKey)}>
                      {busyKey.startsWith("details:") ? "查询中…" : "查找"}
                    </button>
                  </div>
                </form>
              )}
              {detailsMode === "manual" && (
                <form className="stack-form details-form" onSubmit={(event) => {
                  event.preventDefault();
                  const fields = { account_number: accountNumber, account_name: accountName };
                  setAccountNumber("");
                  setAccountName("");
                  void submitDetails("payee", fields);
                }}>
                  <label htmlFor={"account-number-" + task.task_id}>收款账号</label>
                  <input id={"account-number-" + task.task_id} name="payee-account-number" value={accountNumber} onChange={(event) => setAccountNumber(event.target.value)} autoComplete="off" inputMode="numeric" required />
                  <label htmlFor={"account-name-" + task.task_id}>收款人姓名</label>
                  <input id={"account-name-" + task.task_id} name="payee-account-name" value={accountName} onChange={(event) => setAccountName(event.target.value)} autoComplete="off" required />
                  <button className="button button-primary" disabled={Boolean(busyKey)}>
                    {busyKey.startsWith("details:") ? "核对中…" : "安全核对资料"}
                  </button>
                </form>
              )}
              {candidates.length > 0 && (
                <div className="candidate-results">
                  <h5>请选择收款人</h5>
                  {candidates.map((candidate) => (
                    <button className="choice-button candidate-button" key={candidate.payee_id ?? candidate.account_masked} onClick={() => candidate.payee_id && void selectCandidate(candidate.payee_id)} disabled={Boolean(busyKey)}>
                      <span><strong>{candidate.name_masked}</strong><small>{candidate.account_masked} · {candidate.bank_name}</small></span><span aria-hidden="true">›</span>
                    </button>
                  ))}
                </div>
              )}
              {retryKey === "details:" + task.task_id + ":payee_search" && pendingMutations.current.has(retryKey) && (
                <button className="text-button retry-button" onClick={() => void submitDetails("payee_search", {})}>按原查询请求重试</button>
              )}
              {retryKey === "details:" + task.task_id + ":payee" && pendingMutations.current.has(retryKey) && (
                <button className="text-button retry-button" onClick={() => void submitDetails("payee", {})}>按原资料请求重试</button>
              )}
            </div>
          )}
        </div>
      )}

      {activeConfirmation && (
        <div className="interaction-panel confirmation-panel">
          <div className="interaction-heading">
            <span className="step-number">2</span>
            <div><h4>请核对确认单</h4><p>聊天里的“确认”不会批准资金操作。</p></div>
          </div>
          {recordLoading && <p className="muted-copy">正在读取当前确认版本…</p>}
          {confirmation && <>
            <Fields fields={confirmation.display_fields} />
            <p className="expiry-note">确认有效期至 {displayTime(confirmation.expires_at)} · 当前版本 {confirmation.confirmation_version}</p>
            {(canConfirm || canCancel) && confirmation.decision === "pending" && (
              <div className="button-row action-row">
                {canConfirm && <button className="button button-primary" disabled={Boolean(busyKey)} onClick={() => void answerConfirmation("approve")}>
                  {busyKey.startsWith("confirmation:") ? "提交中…" : "确认办理"}
                </button>}
                {canModify && <button className="button button-secondary" disabled={Boolean(busyKey)} onClick={() => setModifying(!modifying)}>修改</button>}
                {canCancel && <button className="button button-danger-outline" disabled={Boolean(busyKey)} onClick={() => setConfirmingCancel(true)}>取消本次操作</button>}
              </div>
            )}
            {confirmingCancel && canCancel && (
              <div className="cancel-confirmation" role="group" aria-label="确认取消转账">
                <p>取消这份确认单后，本次待确认操作将结束。</p>
                <div className="button-row">
                  <button className="button button-danger-outline" disabled={Boolean(busyKey)} onClick={() => void answerConfirmation("cancel")}>确认取消这份操作</button>
                  <button className="button button-secondary" onClick={() => setConfirmingCancel(false)}>保留确认单</button>
                </div>
              </div>
            )}
            {modifying && canModify && (
              <form className="modify-form" onSubmit={(event) => void submitModification(event)}>
                <label htmlFor={"modify-" + task.task_id}>要调整的内容</label>
                <textarea id={"modify-" + task.task_id} name="modification" value={modifyText} onChange={(event) => setModifyText(event.target.value)} rows={2} placeholder="例如：金额改为 300 元" required />
                <p>提交后会先取消这份确认单，再把修改要求放入聊天框；请检查后另行发送。</p>
                <button className="button button-primary" disabled={Boolean(busyKey)}>
                  取消旧确认并准备修改
                </button>
              </form>
            )}
          </>}
          {recordError && <p className="notice notice-error">{recordError}</p>}
        </div>
      )}

      {activeVerification && (
        <div className="interaction-panel verification-panel">
          <div className="interaction-heading">
            <span className="step-number">3</span>
            <div><h4>专用验证</h4><p>验证码不进入聊天，也不会保存在浏览器。</p></div>
          </div>
          {recordLoading && <p className="muted-copy">正在读取当前验证状态…</p>}
          {verification && <>
            {verification.summary && <Fields fields={verification.summary.display_fields} />}
            <div className="verification-status-grid">
              <div><span>验证码</span><strong>{verification.code_result === "passed" ? "已通过" : verification.code_result === "failed" ? "未通过" : "等待输入"}</strong><small>有效期至 {displayTime(verification.code_expires_at)}</small></div>
              {verification.required_methods.includes("mock_face") && <div><span>模拟人脸核验</span><strong>{verification.face_started_at ? verification.face_result === "pending" ? "等待管理员处理" : verification.face_result === "passed" ? "已通过" : "未通过" : "尚未开始"}</strong><small>{verification.face_started_at ? "等待时间以服务端记录为准" : "需要管理员会话作答"}</small></div>}
            </div>
            {canVerify && verification.challenge_status === "pending" && verification.required_methods.includes("code") && (
              <form className="stack-form code-form" onSubmit={(event) => void submitCode(event)}>
                <label htmlFor={"code-" + task.task_id}>验证码（专用输入）</label>
                <div className="inline-form-row">
                  <input id={"code-" + task.task_id} name="verification-code" type="password" inputMode="numeric" autoComplete="one-time-code" spellCheck={false} value={code} onChange={(event) => setCode(event.target.value)} required />
                  <button className="button button-primary">提交验证码</button>
                </div>
                <div className="button-row">
                  <button className="text-button" type="button" onClick={() => void showDemoCode()}>打开模拟验证码提示区</button>
                  <button className="text-button" type="button" onClick={() => void resendCode()} disabled={Boolean(busyKey)}>重新获取</button>
                </div>
                {demoCode && <div className="demo-code-panel" aria-live="polite"><span>本次模拟验证码</span><strong>{demoCode.code}</strong><small>仅在此处显示，30 秒后清除；有效期至 {displayTime(demoCode.expires_at)}</small></div>}
              </form>
            )}
            {canVerify && verification.challenge_status === "pending" && verification.required_methods.includes("mock_face") && !verification.face_started_at && (
              <button className="button button-secondary face-start-button" disabled={Boolean(busyKey)} onClick={() => void startFace()}>
                {busyKey.startsWith("face-start:") ? "正在开始…" : "开始模拟人脸等待"}
              </button>
            )}
            {verification.face_started_at && verification.face_result === "pending" && (
              <a className="admin-face-link" href={administratorUrl({ taskId: task.task_id, challengeId: verification.challenge_id, demoRoundId: task.demo_round_id })}>
                打开独立管理员会话处理模拟人脸 <span aria-hidden="true">↗</span>
              </a>
            )}
          </>}
          {recordError && <p className="notice notice-error">{recordError}</p>}
        </div>
      )}

      {(task.status === "needs_attention" || task.status === "running") && (
        <p className="status-explainer">服务端状态：{task.status}。页面不会把请求受理或等待状态描述为交易成功。</p>
      )}
      {operation && (
        <div className={"bank-result " + (operation.operation_status === "succeeded" ? "bank-result-success" : operation.operation_status === "failed" ? "bank-result-failure" : "bank-result-pending")}>
          <div className="bank-result-heading">
            <div><p className="eyebrow">银行操作结果</p><h4>{operation.operation_status === "succeeded" ? "银行返回成功" : operation.operation_status === "failed" ? "银行返回失败" : "银行仍在处理中"}</h4></div>
            <span className="result-origin">{API_MODE === "contract-demo" ? "测试响应" : "服务端结果"}</span>
          </div>
          {operation.operation_status === "succeeded" && receipt && (
            <Fields fields={[
              { name: "transaction", label: "交易编号", value_text: receipt.transaction_id },
              { name: "payee", label: "收款人", value_text: receipt.payee.name_masked + " · " + receipt.payee.account_masked },
              { name: "amount", label: "金额", value_text: amount(receipt.amount_fen) },
              { name: "completed", label: "完成时间", value_text: displayTime(receipt.completed_at) },
            ]} />
          )}
          {operation.operation_status === "failed" && <p>银行未返回成功。错误代码：{operation.failure?.code ?? "未提供"}</p>}
          {operation.operation_status === "processing" && <p>操作仍在处理中。若结果未知，请查询原操作，不要新建交易。</p>}
        </div>
      )}
      {task.status === "succeeded" && !operation && <p className="notice notice-warning">任务已结束，但当前响应没有银行交易结果；请勿把它当作转账成功。</p>}

      {!activeConfirmation && task.allowed_actions.includes("cancel") && (
        <>
          {!confirmingTaskCancel ? (
            <button className="text-button task-footer-action" disabled={Boolean(busyKey)} onClick={() => setConfirmingTaskCancel(true)}>取消当前任务</button>
          ) : (
            <div className="cancel-confirmation" role="group" aria-label="确认取消当前任务">
              <p>取消只停止尚未执行的操作；已提交或状态未知的操作仍需查询原结果。</p>
              <div className="button-row">
                <button className="button button-danger-outline" disabled={Boolean(busyKey)} onClick={() => { setConfirmingTaskCancel(false); void taskAction("cancel"); }}>确认取消任务</button>
                <button className="button button-secondary" onClick={() => setConfirmingTaskCancel(false)}>继续查看</button>
              </div>
            </div>
          )}
        </>
      )}
      {task.allowed_actions.includes("query") && (
        <button className="button button-secondary task-footer-action" disabled={Boolean(busyKey)} onClick={() => void taskAction("query-result")}>
          {busyKey.startsWith("task:" + task.task_id + ":query-result") ? "查询中…" : "查询原操作结果"}
        </button>
      )}
      {(task.allowed_actions.includes("resume") || task.recovery_required) && (
        <button className="button button-primary task-footer-action" disabled={Boolean(busyKey)} onClick={() => void taskAction("resume")}>恢复原任务</button>
      )}
      {actionError && <div className="notice notice-error" role="alert">{actionError}</div>}
      {retryKey && !retryKey.startsWith("details:") && pendingMutations.current.has(retryKey) && (
        <button className="text-button retry-button" disabled={Boolean(busyKey)} onClick={() => {
          const pending = pendingMutations.current.get(retryKey);
          if (pending) void mutate(retryKey, pending.path, {});
        }}>重试原请求（沿用同一请求编号）</button>
      )}
      <p className="task-id">任务编号：{task.task_id}</p>
    </section>
  );
}
