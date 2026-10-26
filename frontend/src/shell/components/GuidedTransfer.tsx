import { useEffect, useState } from "react";
import type { AccountList, PayeeList, TransferTaskView } from "../../contracts";
import type { ShellTask } from "../types";
import type { Conversation } from "../useConversation";
import { yuan } from "../format";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Check, ChevronRight, Plus, Search } from "lucide-react";

export function transferDraft(task: ShellTask): TransferTaskView | null {
  return (!task.module || task.module === "transfer") && task.data && typeof task.data === "object" && "amount_fen" in task.data
    ? task.data as TransferTaskView : null;
}

export function GuidedTransfer({ task, conversation, busy }: { task: ShellTask; conversation: Conversation; busy: boolean }) {
  const data = transferDraft(task)!;
  const [accounts, setAccounts] = useState<AccountList["accounts"]>([]);
  const [payees, setPayees] = useState<PayeeList["payees"]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [reload, setReload] = useState(0);
  const [edit, setEdit] = useState<"amount" | "account" | "payee" | null>(null);
  const [amount, setAmount] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [manual, setManual] = useState(false);
  const [name, setName] = useState("");
  const [number, setNumber] = useState("");
  const [showSummary, setShowSummary] = useState(false);
  const id = "guided-" + task.task_id;
  const editable = !data.operation && !task.recovery_required && !conversation.expired
    && (task.status === "waiting_input" || task.status === "waiting_approval" && task.interaction?.kind === "confirmation");
  useEffect(() => {
    if (!editable || !conversation.readTransferChoices) { setLoading(false); return; }
    let active = true;
    setLoading(true); setLoadError("");
    Promise.all([conversation.readTransferChoices(task.task_id, "accounts"), conversation.readTransferChoices(task.task_id, "payees")])
      .then(([a, p]) => { if (active) { setAccounts("accounts" in a ? a.accounts : []); setPayees("payees" in p ? p.payees : []); } })
      .catch(() => { if (active) setLoadError("暂时没有读到账户和收款人。已填资料仍在，请重新读取。"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [task.task_id, conversation.readTransferChoices, editable, reload]);
  const chosenAccount = accounts.find((item) => item.account_id === data.payer_account_id);
  // A payee is displayed only after bank verification. Missing display data does
  // not mean the server is asking for it again; its input request owns the step.
  const field = task.interaction?.kind === "input" ? task.interaction.required_fields[0] : undefined;
  const current = edit ?? (field === "amount_fen" ? "amount" : field === "payer_account_id" ? "account" : field === "payee_hint" ? "payee" : null);
  const view = task.interaction?.record_ref ? conversation.confirmations[task.interaction.record_ref] : undefined;
  async function save(changes: Parameters<Conversation["actions"]["reviseDraft"]>[2]) {
    setError("");
    if (await conversation.actions.reviseDraft(task, view, changes)) { setEdit(null); setShowSummary(false); setManual(false); setName(""); setNumber(""); }
  }
  const listed = payees.filter((item) => [item.remark, item.name_masked, item.bank_name, item.account_masked].join(" ").includes(search.trim()));
  if (!editable) return null;
  const confirming = task.interaction?.kind === "confirmation";
  const prompt = current === "payee" ? "这笔钱转给谁？" : current === "amount" ? "这次转多少钱？" : current === "account" ? "用哪张银行卡？" : "已填的转账资料";
  if (!current && !confirming && !data.amount_fen && !data.payer_account_id && !data.payee) return null;
  return <section className={"sh-guided" + (confirming ? " sh-guided-edit" : "")} aria-labelledby={id} aria-busy={busy || loading}>
    <h3 id={id} className={confirming && !edit ? "sr-only" : undefined}>{confirming && !edit ? "修改转账资料" : prompt}</h3>
    {confirming && <Button variant="outline" onClick={() => setShowSummary(!showSummary)} aria-expanded={showSummary} aria-controls={id + "-summary"}>修改转账资料</Button>}
    <dl id={id + "-summary"} className="sh-draft-summary" hidden={confirming && !showSummary}>
      {([
        ["account", "付款卡", chosenAccount ? chosenAccount.display_name + " · " + chosenAccount.account_masked : data.payer_account_id ? "已选付款账户（确认单可核对）" : "待选择"],
        ["payee", "转给谁", data.payee ? (data.payee.remark || data.payee.name_masked) + " · " + data.payee.bank_name + " · " + data.payee.account_masked : "待选择"],
        ["amount", "金额", data.amount_fen ? yuan(data.amount_fen) : "待填写"],
      ] as const).filter(([, , value]) => !value.startsWith("待") || confirming).map(([key, label, value]) => <div key={key}><dt>{label}</dt><dd>{value}</dd>
        <button className="sh-link-btn" type="button" disabled={busy} aria-label={"修改" + label} onClick={() => { setEdit(key); setError(""); setAmount(data.amount_fen ? String(data.amount_fen / 100) : ""); }}>修改</button></div>)}
    </dl>
    {loading && <div role="status"><p>正在读取您的账户和收款人…</p><div aria-hidden="true" className="sh-loading-choices"><Skeleton /><Skeleton /></div></div>}
    {loadError && <div role="alert"><p>{loadError}</p><button className="sh-btn sh-btn-secondary" onClick={() => setReload((n) => n + 1)}>重新读取</button></div>}
    {editable && current === "amount" && <form className="sh-guided-form" onSubmit={(event) => {
      event.preventDefault();
      const value = Number(amount) * 100;
      if (!/^\d+(?:\.\d{1,2})?$/.test(amount) || !Number.isSafeInteger(Math.round(value)) || value <= 0) { setError("请填写大于零的金额，最多两位小数。"); return; }
      void save({ amount_fen: Math.round(value) });
    }}><label htmlFor={id + "-amount"}>转账金额（元）</label><Input id={id + "-amount"} inputMode="decimal" value={amount} onChange={(event) => setAmount(event.target.value)} disabled={busy} autoComplete="off" aria-invalid={Boolean(error)} aria-describedby={error ? id + "-error" : undefined} placeholder="请输入金额" />
      <div className="sh-amount-shortcuts" aria-label="常用金额">{[100, 500, 1000].map((value) => <Button type="button" variant="outline" key={value} disabled={busy} onClick={() => setAmount(String(value))}>{value} 元</Button>)}</div>
      <Button disabled={busy || !amount}>用这个金额<ChevronRight aria-hidden="true" /></Button></form>}
    {editable && current === "account" && !loading && <div className="sh-choice-list" aria-label="选择付款账户">
      {!loadError && accounts.length === 0 && <p>没有查到可用账户，请稍后重新读取。</p>}
      {accounts.map((item) => <button type="button" className="sh-choice" key={item.account_id} disabled={busy} aria-pressed={data.payer_account_id === item.account_id} onClick={() => void save({ payer_account_id: item.account_id })}>
        <strong>{item.display_name} · {item.account_masked}</strong><span>{item.bank_name} · 可用余额 {yuan(item.available_balance_fen)}</span></button>)}
      <p className="sh-hint">可用余额以银行办理时为准。</p>
    </div>}
    {editable && current === "payee" && !loading && <div>
      <label className="sr-only" htmlFor={id + "-search"}>查找已保存的收款人</label><div className="sh-search-field"><Search aria-hidden="true" /><Input id={id + "-search"} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="找姓名、备注或尾号" /></div>
      <div className="sh-choice-list">{listed.map((item, index) => <button type="button" className="sh-choice sh-person-choice" key={item.payee_id ?? index} disabled={busy || !item.payee_id} onClick={() => void save({ payee_id: item.payee_id! })}>
        <span className="sh-person-initial" aria-hidden="true">{(item.remark || item.name_masked).slice(0, 1)}</span>
        <span><strong>{item.remark || item.name_masked}</strong><span>{item.name_masked} · {item.bank_name} · {item.account_masked}</span></span>
        {data.payee?.payee_id === item.payee_id ? <Check aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}</button>)}</div>
      {!loadError && listed.length === 0 && <p>{payees.length ? "没有匹配的收款人，请换个备注或尾号。" : "您还没有已保存的收款人。"}</p>}
      {conversation.supportsDetails && task.interaction?.kind === "input" && task.interaction.required_fields.includes("payee_hint") && <Button type="button" variant="outline" disabled={busy} onClick={() => setManual(!manual)}><Plus aria-hidden="true" />填写新的收款人</Button>}
      {manual && <form className="sh-guided-form" onSubmit={async (event) => { event.preventDefault(); if (await conversation.actions.submitPayeeDetails(task, { account_name: name.trim(), account_number: number.trim() })) { setName(""); setNumber(""); setManual(false); } }}>
        <p className="sh-hint">请在这个表单里填写收款资料。</p>
        <label htmlFor={id + "-name"}>收款人姓名</label><input id={id + "-name"} value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" disabled={busy} required />
        <label htmlFor={id + "-number"}>收款银行卡号</label><input id={id + "-number"} value={number} onChange={(event) => setNumber(event.target.value)} autoComplete="off" inputMode="numeric" disabled={busy} required />
        <button className="sh-btn sh-btn-primary" disabled={busy}>核对收款资料</button>
      </form>}
    </div>}
    {error && <p id={id + "-error"} role="alert">{error}</p>}
    {editable && edit && <button type="button" className="sh-btn sh-btn-quiet" disabled={busy} onClick={() => { setEdit(null); setManual(false); setName(""); setNumber(""); }}>收起修改</button>}
  </section>;
}
