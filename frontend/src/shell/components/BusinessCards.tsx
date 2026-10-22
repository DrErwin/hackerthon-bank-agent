import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { AccountList, BillDetails, BillReport, PayeeList, SpendingSummary, SubscriptionTaskView } from "../../contracts";
import { yuan } from "../format";
import type { CardSelection, ShellTask } from "../types";
import { Card, FieldList } from "./Primitives";
import { selectionKey, type CardLink } from "../presentation";
import { DetailsDrawer } from "./DetailsDrawer";

interface InlineActions {
  links?: CardLink[];
  renderChild?: (id: string) => ReactNode;
  activeChildren?: string[];
}

function dateLabel(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("zh-CN", { timeZone: "Asia/Shanghai" });
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
      }}><span>{pending ? "正在打开…" : open ? "收起 · " + label : label}</span>{amount && <strong>{amount}</strong>}</button>
      {open && childId && <div id={panelId} className="sh-inline-result">{renderChild?.(childId) ?? <p>已打开这项办理。</p>}</div>}
  </div>;
}

export function BusinessCards({ task, busy, enabled, onAction, links, renderChild, activeChildren }: {
  task: ShellTask; busy: boolean; enabled: boolean;
  onAction: (selection: CardSelection) => Promise<string | null>;
} & InlineActions) {
  const data = businessPayload(task);
  const id = "task-" + task.task_id + "-business";
  if (!data) return null;
  if ("accounts" in data) return <Card title="我的账户" labelledBy={id}>
    {data.accounts.length === 0 && <p>没有查到可展示的账户。</p>}
    {data.accounts.map((item) => <div className="sh-business-row" key={item.account_id}>
      <div className="sh-row-heading"><strong>{item.display_name}</strong><strong>{yuan(item.available_balance_fen)}</strong></div>
      <p className="sh-hint">{item.bank_name} · {item.account_masked} · 可用余额</p>
    </div>)}
  </Card>;
  if ("payees" in data) return <Card title="常用收款人" labelledBy={id}>
    {data.payees.length === 0 && <p>没有查到常用收款人。</p>}
    {data.payees.map((item, index) => <div className="sh-business-row" key={item.payee_id ?? index}>
      <details className="sh-disclosure"><summary>{item.remark || item.name_masked} <span className="sh-hint">{item.bank_name}</span></summary>
        <p>{item.name_masked} · {item.account_masked}</p>
      </details>
    </div>)}
  </Card>;
  if (data.action === "cancel") {
    const receipt = data.operation?.receipt;
    return <Card title="订阅办理结果" labelledBy={id}>
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
    <p className="sh-lead">有 {list.active_count} 项自动扣费，近期合计 {yuan(list.upcoming_total_fen)}。</p>
    <p className="sh-hint">这是查询时的记录。退订是否成功，请看该项目的办理结果。</p>
    {([['active', '有效签约'], ['suspected', '疑似周期扣款'], ['cancelled', '已退订']] as const).map(([status, label]) =>
      <section key={status} aria-label={label}>
        <details className="sh-disclosure" open={status === "active" ? true : undefined}>
        <summary>{status === "active" ? "正在扣费" : label}（{list.items.filter((item) => item.status === status).length}）</summary>
        {list.items.filter((item) => item.status === status).length === 0 && <p className="sh-hint">暂无项目</p>}
        {list.items.filter((item) => item.status === status).map((item) => <div className="sh-business-row" key={item.subscription_id}>
          <div className="sh-row-heading"><strong>{item.service_name}</strong><span>{yuan(item.amount_fen)} / {item.cycle === "monthly" ? "月" : "年"}</span></div>
          <details className="sh-disclosure"><summary>扣费信息</summary>
            <p>{item.merchant_name} · {item.account_masked}</p>
            {item.next_billing_at && <p>下次扣费：{dateLabel(item.next_billing_at)}</p>}
          </details>
          {status === "suspected" && <p className="sh-hint">根据流水发现的线索，尚未确认银行签约。{item.external_cancel_guide}</p>}
          {enabled && item.status === "active" && item.source_type === "mandate" && item.can_cancel_in_bank &&
            <ActionButton label={"取消「" + item.service_name + "」"} busy={busy}
              selection={{ action: "subscription_cancel", subscription_id: item.subscription_id }} onAction={onAction} links={links} renderChild={renderChild} activeChildren={activeChildren} />}
        </div>)}
        </details>
      </section>)}
    {list.suspected_scan_status === "insufficient_data" && <p className="sh-hint">流水资料不足，疑似周期扣款尚未完整核对。</p>}
    <p className="sh-hint">查询日期：{dateLabel(list.as_of)}</p>
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

function TransactionRows({ items }: { items: BillDetails["transactions"] }) {
  const natures = { consumption: "消费", refund: "退款", transfer: "转账", interest: "利息" };
  return <div className="sh-transaction-list">{items.map((item) => <details className="sh-disclosure sh-transaction" key={item.transaction_id}>
    <summary><span>{item.counterparty_name}<small>{natures[item.nature]} · {item.direction === "inflow" ? "收入" : "支出"}</small></span><strong>{yuan(item.amount_fen)}</strong></summary>
    <p>{new Date(item.occurred_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })}</p>
    <p>分类：{CATEGORY_LABEL[item.category]}</p>
    {item.summary && <p>{item.summary}</p>}
    {item.counterparty_account_masked && <p>对方账户：{item.counterparty_account_masked}</p>}
  </details>)}</div>;
}

export function BillDetailsCard({ task, demo }: { task: ShellTask; demo: boolean }) {
  const data = billDetails(task);
  if (!data) return null;
  const title = (data.category ? CATEGORY_LABEL[data.category] : "账单") + "明细";
  return <Card title={title} labelledBy={"task-" + task.task_id + "-details"}>
    <p className="sh-hint">共 {data.transactions.length} 笔，点一笔查看说明。</p>
    <TransactionRows items={data.transactions.slice(0, 3)} />
    {data.transactions.length > 3 && <DetailsDrawer title={"查看全部 " + data.transactions.length + " 笔明细"}>
      <TransactionRows items={data.transactions} />
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
  const summary = billSummary(task);
  if (!summary) return null;
  return <Card title="这段时间花了多少钱" labelledBy={"task-" + task.task_id + "-bill-actions"}>
    <p className="sh-hint">{new Date(summary.scope.start_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })} 至 {new Date(summary.scope.end_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })}（结束时刻不计入） · {summary.scope.account_ids.length} 张卡</p>
    <div className="sh-row-heading sh-bill-total"><span>消费扣除退款后</span><strong>{yuan(summary.consumption_net_fen)}</strong></div>
    <p className="sh-hint">共 {summary.transaction_count} 笔记录。点下面的分类，就能查看明细。</p>
    <div className="sh-business-actions">
      {summary.categories.map((item) => <div className="sh-category-row" key={item.category}>
        {!enabled && <div className="sh-row-heading"><strong>{CATEGORY_LABEL[item.category]}</strong><span>{yuan(item.net_fen)}</span></div>}
        {enabled && <ActionButton label={"查看" + CATEGORY_LABEL[item.category] + "明细"} amount={yuan(item.net_fen)} busy={busy}
          selection={{ action: "bill_details", category: item.category }} onAction={onAction} links={links} renderChild={renderChild} activeChildren={activeChildren} />}
      </div>)}
      {enabled && <ActionButton label="核对陌生扣款" busy={busy} selection={{ action: "bill_check" }} onAction={onAction} links={links} renderChild={renderChild} activeChildren={activeChildren} />}
    </div>
    {details && <DetailsDrawer title="查看完整账单说明">{details}</DetailsDrawer>}
    {demo && <p className="sh-demo-note">演示数据，不代表真实账单。</p>}
  </Card>;
}
