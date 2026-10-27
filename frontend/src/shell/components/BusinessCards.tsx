import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { AccountList, BillDetails, BillReport, PayeeList, SpendingSummary, SubscriptionTaskView } from "../../contracts";
import { yuan } from "../format";
import type { CardSelection, DraftChanges, ShellTask } from "../types";
import { Card, FieldList } from "./Primitives";
import { selectionKey, taskTitle, type CardLink } from "../presentation";
import { DetailsDrawer } from "./DetailsDrawer";
import { ArrowDownLeft, ArrowUpRight, ChevronDown, ChevronRight, CreditCard, RefreshCw, Search, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface InlineActions {
  links?: CardLink[];
  renderChild?: (id: string) => ReactNode;
  activeChildren?: string[];
}

function dateLabel(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("zh-CN", { timeZone: "Asia/Shanghai" });
}

export function billPeriod(start: string, end: string) {
  const stop = new Date(end);
  const midnight = stop.toLocaleTimeString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false }) === "00:00:00";
  return dateLabel(start) + " 至 " + dateLabel(midnight ? new Date(stop.getTime() - 1).toISOString() : end);
}

export function QueryRefresh({ busy, onAction }: { busy: boolean; onAction: (selection: CardSelection) => Promise<string | null> }) {
  return <Button type="button" variant="outline" className="sh-refresh" disabled={busy} onClick={() => void onAction({ action: "refresh_query" })}><RefreshCw aria-hidden="true" />{busy ? "正在查询…" : "重新查询最新资料"}</Button>;
}

function SearchField({ id, label, value, onChange }: { id: string; label: string; value: string; onChange: (value: string) => void }) {
  return <div className="sh-list-search"><label htmlFor={id}>{label}</label><div><Search aria-hidden="true" />
    <Input id={id} type="search" value={value} onChange={(event) => onChange(event.target.value)} autoComplete="off" />
  </div></div>;
}

type Payload = AccountList | PayeeList | SubscriptionTaskView;

// Module-independent TaskView.data is narrowed using the public result shape.
export function businessPayload(task: ShellTask): Payload | null {
  if (task.status !== "succeeded" || !task.data || typeof task.data !== "object") return null;
  const data = task.data;
  if ("accounts" in data && Array.isArray(data.accounts)) return data as AccountList;
  if ("payees" in data && Array.isArray(data.payees)) return data as PayeeList;
  if ("action" in data && (data.action === "list" || data.action === "cancel")) return data as SubscriptionTaskView;
  return null;
}

function ActionButton({ label, busy, selection, onAction, links = [], renderChild, activeChildren = [], amount }: {
  label: string; busy: boolean; selection: CardSelection;
  amount?: string;
  onAction: (selection: CardSelection) => Promise<string | null>;
} & InlineActions) {
  const [child, setChild] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const restoreFocus = useRef(false);
  const panelId = useId();
  const [expanded, setOpen] = useState(false);
  const childId = child ?? links.find((link) => selectionKey(link.selection) === selectionKey(selection))?.childId;
  const open = expanded || Boolean(childId && activeChildren.includes(childId));
  const childNeedsAttention = Boolean(childId && activeChildren.includes(childId));
  useEffect(() => { if (childNeedsAttention) setOpen(true); }, [childNeedsAttention]);
  useEffect(() => {
    if (!pending && !busy && restoreFocus.current) {
      if (document.activeElement === document.body) trigger.current?.focus();
      restoreFocus.current = false;
    }
  }, [pending, busy]);
  return <div className="sh-business-action">
      <button type="button" ref={trigger} className="sh-btn sh-btn-secondary" aria-label={label} aria-expanded={open} aria-controls={open ? panelId : undefined} disabled={busy || pending} onClick={async () => {
        if (childId) { setOpen(!open); return; }
        restoreFocus.current = document.activeElement === trigger.current;
        setPending(true);
        try { const id = await onAction(selection); setChild(id); if (id) setOpen(true); } finally { setPending(false); }
      }}><span>{pending ? "正在打开…" : label}</span>{amount && <strong>{amount}</strong>}{open ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}</button>
      {open && childId && <div id={panelId} className="sh-inline-result">{renderChild?.(childId) ?? <p>已打开这项办理。</p>}</div>}
  </div>;
}

export function BusinessCards({ task, busy, enabled, onAction, links, renderChild, activeChildren, transferTargets = [], onChoose, targetBusy = {}, targetErrors = {} }: {
  task: ShellTask; busy: boolean; enabled: boolean;
  transferTargets?: ShellTask[];
  onChoose?: (task: ShellTask, changes: DraftChanges) => Promise<void>;
  targetBusy?: Record<string, string>; targetErrors?: Record<string, string>;
  onAction: (selection: CardSelection) => Promise<string | null>;
} & InlineActions) {
  const [chosenRow, setChosenRow] = useState("");
  const [search, setSearch] = useState("");
  const matches = (...values: (string | null | undefined)[]) => values.some((value) => value?.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()));
  const data = businessPayload(task);
  const id = "task-" + task.task_id + "-business";
  if (!data) return null;
  if ("accounts" in data) return <Card title="我的账户" labelledBy={id}>
    <p className="sh-hint">查询时可用余额 · {data.accounts.length} 张银行卡</p>
    {data.accounts.length > 1 && <SearchField id={id + "-search"} label="找银行卡" value={search} onChange={setSearch} />}
    {data.accounts.length === 0 && <p className="sh-empty">还没有可展示的账户。可以重新查询。</p>}
    {search && !data.accounts.some((item) => matches(item.display_name, item.bank_name, item.account_masked)) && <p role="status" className="sh-empty">没有找到这张卡，试试银行名称或尾号。</p>}
    {data.accounts.filter((item) => matches(item.display_name, item.bank_name, item.account_masked)).map((item) => <div className="sh-business-row sh-account-row" key={item.account_id}>
      <div className="sh-row-heading"><strong><CreditCard aria-hidden="true" />{item.display_name}</strong><strong>{yuan(item.available_balance_fen)}</strong></div>
      <p className="sh-hint">{item.bank_name} · {item.account_masked}</p>
      {onChoose && transferTargets.map((target) => <div key={target.task_id}><button type="button" className="sh-btn sh-btn-secondary" disabled={busy || Boolean(targetBusy[target.task_id])}
        onClick={() => { setChosenRow(item.account_id + target.task_id); void onChoose(target, { payer_account_id: item.account_id }); }}>{targetBusy[target.task_id] ? "正在更新…" : "用" + item.display_name + " · " + taskTitle(target)}</button>
        {chosenRow === item.account_id + target.task_id && targetErrors[target.task_id] && <p role="alert">{targetErrors[target.task_id]}</p>}</div>)}
    </div>)}
    {enabled && <QueryRefresh busy={busy} onAction={onAction} />}
  </Card>;
  if ("payees" in data) return <Card title="常用收款人" labelledBy={id}>
    {data.payees.length > 0 && <SearchField id={id + "-search"} label="找收款人（姓名、备注或尾号）" value={search} onChange={setSearch} />}
    {data.payees.length === 0 && <p className="sh-empty">还没有常用收款人。转账时可以填写新的收款资料。</p>}
    {search && !data.payees.some((item) => matches(item.remark, item.name_masked, item.bank_name, item.account_masked)) && <p role="status" className="sh-empty">没有找到这位收款人，试试备注或尾号。</p>}
    {data.payees.filter((item) => matches(item.remark, item.name_masked, item.bank_name, item.account_masked)).map((item, index) => <div className="sh-business-row sh-payee-row" key={item.payee_id ?? index}>
      <strong><UserRound aria-hidden="true" />{item.remark || item.name_masked}</strong>
      <p className="sh-hint">{item.name_masked} · {item.bank_name} · {item.account_masked}</p>
      {onChoose && item.payee_id && transferTargets.map((target) => <div key={target.task_id}><button type="button" className="sh-btn sh-btn-secondary" disabled={busy || Boolean(targetBusy[target.task_id])}
        onClick={() => { setChosenRow(item.payee_id! + target.task_id); void onChoose(target, { payee_id: item.payee_id! }); }}>{targetBusy[target.task_id] ? "正在更新…" : "选择" + (item.remark || item.name_masked) + " · " + taskTitle(target)}</button>
        {chosenRow === item.payee_id + target.task_id && targetErrors[target.task_id] && <p role="alert">{targetErrors[target.task_id]}</p>}</div>)}
    </div>)}
    {transferTargets.length === 0 && data.payees.length > 0 && <p className="sh-hint">转账时，可以直接选择这些收款人。</p>}
    {enabled && <QueryRefresh busy={busy} onAction={onAction} />}
  </Card>;
  if (data.action === "cancel") {
    const receipt = data.operation?.receipt;
    return <Card title="自动扣费办理结果" labelledBy={id}>
      <p>{task.message}</p>
      {receipt && <FieldList fields={[
        { name: "service", label: "已退订服务", value_text: receipt.merchant_name + " · " + receipt.service_name },
        { name: "account", label: "扣款账户", value_text: receipt.account_masked },
        { name: "stop", label: "停止扣款生效时间", value_text: new Date(receipt.effective_stop_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai" }) },
      ]} />}
    </Card>;
  }
  const list = data.list_result;
  if (!list) return null;
  return <Card title="订阅与自动扣款" labelledBy={id}>
    <div className="sh-summary-pair"><div><span>正在扣费</span><strong>{list.active_count} 项</strong></div><div><span>近期将扣</span><strong>{yuan(list.upcoming_total_fen)}</strong></div></div>
    {list.items.length > 0 && <SearchField id={id + "-search"} label="找服务或商户" value={search} onChange={setSearch} />}
    {list.items.length === 0 && <p className="sh-empty">这次没有查到自动扣费项目。</p>}
    {search && !list.items.some((item) => matches(item.service_name, item.merchant_name, item.account_masked)) && <p role="status" className="sh-empty">没有找到这项服务，试试商户名称。</p>}
    {([['active', '有效签约'], ['suspected', '疑似周期扣款'], ['cancelled', '已退订']] as const).map(([status, label]) =>
      <section key={status} aria-label={label}>
        <details className="sh-disclosure" open={status === "active" || Boolean(search) ? true : undefined}>
        <summary>{status === "active" ? "正在扣费" : label}（{list.items.filter((item) => item.status === status).length}）</summary>
        {list.items.filter((item) => item.status === status).length === 0 && <p className="sh-hint">暂无项目</p>}
        {list.items.filter((item) => item.status === status && matches(item.service_name, item.merchant_name, item.account_masked)).map((item) => <div className="sh-business-row" key={item.subscription_id}>
          <div className="sh-row-heading"><strong>{item.service_name}</strong><span>{yuan(item.amount_fen)} / {item.cycle === "monthly" ? "月" : "年"}</span></div>
          <div className="sh-hint">
            <p>{item.merchant_name} · {item.account_masked}</p>
            {item.next_billing_at && <p>下次扣费：{dateLabel(item.next_billing_at)}</p>}
          </div>
          {status === "suspected" && <p className="sh-hint">这笔扣款看起来会重复发生，请到商户核实。{item.external_cancel_guide}</p>}
          {enabled && item.status === "active" && item.source_type === "mandate" && item.can_cancel_in_bank &&
            <ActionButton label={"取消「" + item.service_name + "」"} busy={busy}
              selection={{ action: "subscription_cancel", subscription_id: item.subscription_id }} onAction={onAction} links={links} renderChild={renderChild} activeChildren={activeChildren} />}
        </div>)}
        </details>
      </section>)}
    {list.suspected_scan_status === "insufficient_data" && <p className="sh-hint">流水资料不足，疑似周期扣款尚未完整核对。</p>}
    <p className="sh-hint">查询日期：{dateLabel(list.as_of)}</p>
    {enabled && <QueryRefresh busy={busy} onAction={onAction} />}
  </Card>;
}

const CATEGORY_LABEL: Record<SpendingSummary["categories"][number]["category"], string> = {
  dining: "餐饮", transport: "交通", medical: "医疗", shopping: "购物", housing: "居住", transfer: "转账", other: "其他",
};

export function billDetails(task: ShellTask): BillDetails | null {
  const data = task.data;
  return task.status === "succeeded" && data && typeof data === "object" && "transactions" in data
    && Array.isArray(data.transactions) && "scope" in data ? data as BillDetails : null;
}

function TransactionRows({ items, busy, onAction, ...inline }: { items: BillDetails["transactions"]; busy?: boolean; onAction?: (selection: CardSelection) => Promise<string | null> } & InlineActions) {
  const natures = { consumption: "消费", refund: "退款", transfer: "转账", interest: "利息" };
  return <div className="sh-transaction-list">{items.map((item) => <details className="sh-disclosure sh-transaction" key={item.transaction_id}
    open={inline.links?.some((link) => link.selection.transaction_id === item.transaction_id) || undefined}>
    <summary><span>{item.counterparty_name}<small>{dateLabel(item.occurred_at)} · {natures[item.nature]}</small></span><strong className="sh-transaction-amount">{item.direction === "inflow" ? <ArrowDownLeft aria-hidden="true" /> : <ArrowUpRight aria-hidden="true" />}<span><small>{item.direction === "inflow" ? "收入" : "支出"}</small>{yuan(item.amount_fen)}</span></strong></summary>
    <p>{new Date(item.occurred_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })}</p>
    <p>分类：{CATEGORY_LABEL[item.category]}</p>
    {item.summary && <p>{item.summary}</p>}
    {item.counterparty_account_masked && <p>对方账户：{item.counterparty_account_masked}</p>}
    {onAction && <>
      <ActionButton label="核对这笔扣款" busy={Boolean(busy)} selection={{ action: "bill_check", transaction_id: item.transaction_id, account_id: item.account_id }} onAction={onAction} {...inline} /></>}
  </details>)}</div>;
}

export function BillDetailsCard({ task, demo, busy, onAction, ...inline }: { task: ShellTask; demo: boolean; busy?: boolean; onAction?: (selection: CardSelection) => Promise<string | null> } & InlineActions) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const data = billDetails(task);
  if (!data) return null;
  const title = (data.category ? CATEGORY_LABEL[data.category] : "账单") + "明细";
  return <Card title={title} labelledBy={"task-" + task.task_id + "-details"}>
    <p className="sh-hint">{billPeriod(data.scope.start_at, data.scope.end_at)} · 共 {data.transactions.length} 笔</p>
    {data.transactions.length === 0 && <p className="sh-empty">这段时间没有这类记录。可以换个时间再看看。</p>}
    <TransactionRows items={data.transactions.filter((item, index) => index < 3 || inline.links?.some((link) =>
      link.selection.transaction_id === item.transaction_id))} busy={busy} onAction={onAction} {...inline} renderChild={drawerOpen ? undefined : inline.renderChild} />
    {data.transactions.length > 3 && <DetailsDrawer title={"查看全部 " + data.transactions.length + " 笔明细"} onOpenChange={setDrawerOpen}>
      <TransactionRows items={data.transactions} busy={busy} onAction={onAction} {...inline} />
    </DetailsDrawer>}
    <p className="sh-hint">查询日期：{dateLabel(data.as_of)}</p>
    {demo && <p className="sh-demo-note">演示数据，不代表真实账单。</p>}
  </Card>;
}

export function billSummary(task: ShellTask): SpendingSummary | null {
  if (task.status !== "succeeded" || !task.data || typeof task.data !== "object") return null;
  const data = task.data;
  const summary = "report_id" in data ? (data as BillReport).summary : data as SpendingSummary;
  return Array.isArray(summary?.categories) ? summary : null;
}

export function BillCardActions({ task, busy, onAction, links, renderChild, activeChildren, enabled = true, details, demo = false }: {
  task: ShellTask; busy: boolean; onAction: (selection: CardSelection) => Promise<string | null>;
  enabled?: boolean; details?: ReactNode; demo?: boolean;
} & InlineActions) {
  const [month, setMonth] = useState("");
  const summary = billSummary(task);
  if (!summary) return null;
  return <Card title="这段时间花了多少钱" labelledBy={"task-" + task.task_id + "-bill-actions"}>
    <p className="sh-hint">{billPeriod(summary.scope.start_at, summary.scope.end_at)} · {summary.scope.account_ids.length} 张卡</p>
    <div className="sh-row-heading sh-bill-total"><span>消费扣除退款后</span><strong>{yuan(summary.consumption_net_fen)}</strong></div>
    <p className="sh-hint">共 {summary.transaction_count} 笔记录</p>
    {enabled && <details className="sh-disclosure sh-bill-filter"><summary>换一个月份</summary><form className="sh-guided-form" onSubmit={(event) => { event.preventDefault(); if (month && !busy) void onAction({ action: "bill_range", month }); }}>
      <label htmlFor={"month-" + task.task_id}>查询月份（沿用这些银行卡）</label>
      <Input id={"month-" + task.task_id} type="month" value={month} onInput={(event) => setMonth(event.currentTarget.value)} required disabled={busy} />
      <Button type="submit" variant="outline" disabled={busy || !month}>{busy ? "正在查询…" : "查询这个月"}</Button>
    </form></details>}
    {summary.transaction_count === 0 && <p className="sh-empty">这段时间没有账单记录。可以换个月份看看。</p>}
    <div className="sh-business-actions">
      {summary.categories.map((item) => <div className="sh-category-row" key={item.category}>
        {!enabled && <div className="sh-row-heading"><strong>{CATEGORY_LABEL[item.category]}</strong><span>{yuan(item.net_fen)}</span></div>}
        {enabled && <ActionButton label={"查看" + CATEGORY_LABEL[item.category] + "明细"} amount={yuan(item.net_fen)} busy={busy}
          selection={{ action: "bill_details", category: item.category }} onAction={onAction} links={links} renderChild={renderChild} activeChildren={activeChildren} />}
      </div>)}
      {enabled && <ActionButton label="核对陌生扣款" busy={busy} selection={{ action: "bill_check" }} onAction={onAction} links={links} renderChild={renderChild} activeChildren={activeChildren} />}
    </div>
    {details && <DetailsDrawer title="查看完整账单说明">{details}</DetailsDrawer>}
    <p className="sh-hint">查询日期：{dateLabel(summary.as_of)}</p>
    {enabled && <QueryRefresh busy={busy} onAction={onAction} />}
    {demo && <p className="sh-demo-note">演示数据，不代表真实账单。</p>}
  </Card>;
}
