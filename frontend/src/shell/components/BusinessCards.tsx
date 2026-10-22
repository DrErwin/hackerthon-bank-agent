import { useState } from "react";
import type { AccountList, BillReport, PayeeList, SpendingSummary, SubscriptionTaskView } from "../../contracts";
import { yuan } from "../format";
import type { CardSelection, ShellTask } from "../types";
import { Card, FieldList } from "./Primitives";

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

function ActionButton({ label, busy, selection, onAction }: {
  label: string; busy: boolean; selection: CardSelection;
  onAction: (selection: CardSelection) => Promise<string | null>;
}) {
  const [child, setChild] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  return <div className="sh-business-action">
    {child ? <a className="sh-btn sh-btn-secondary" href={"#task-" + child}>查看已打开的办理</a> :
      <button type="button" className="sh-btn sh-btn-secondary" disabled={busy || pending} onClick={async () => {
        setPending(true);
        try { setChild(await onAction(selection)); } finally { setPending(false); }
      }}>{pending ? "正在打开…" : label}</button>}
  </div>;
}

export function BusinessCards({ task, busy, enabled, onAction }: {
  task: ShellTask; busy: boolean; enabled: boolean;
  onAction: (selection: CardSelection) => Promise<string | null>;
}) {
  const data = businessPayload(task);
  const id = "task-" + task.task_id + "-business";
  if (!data) return null;
  if ("accounts" in data) return <Card title="我的账户" labelledBy={id}>
    {data.accounts.length === 0 && <p>没有查到可展示的账户。</p>}
    {data.accounts.map((item) => <div className="sh-business-row" key={item.account_id}>
      <h4>{item.display_name}</h4>
      <FieldList fields={[
        { name: "bank", label: "银行", value_text: item.bank_name },
        { name: "account", label: "账户", value_text: item.account_masked },
        { name: "balance", label: "可用余额", value_text: yuan(item.available_balance_fen) },
      ]} />
    </div>)}
  </Card>;
  if ("payees" in data) return <Card title="常用收款人" labelledBy={id}>
    {data.payees.length === 0 && <p>没有查到常用收款人。</p>}
    {data.payees.map((item, index) => <div className="sh-business-row" key={item.payee_id ?? index}>
      <h4>{item.remark || item.name_masked}</h4>
      <FieldList fields={[
        { name: "name", label: "姓名", value_text: item.name_masked },
        { name: "bank", label: "银行", value_text: item.bank_name },
        { name: "account", label: "账户", value_text: item.account_masked },
      ]} />
    </div>)}
  </Card>;
  if (data.action === "cancel") {
    const receipt = data.operation?.receipt;
    return <Card title="订阅办理结果" labelledBy={id}>
      <p>{task.message}</p>
      {receipt && <FieldList fields={[
        { name: "service", label: "已退订服务", value_text: receipt.merchant_name + " · " + receipt.service_name },
        { name: "account", label: "扣款账户", value_text: receipt.account_masked },
        { name: "stop", label: "停止扣款生效时间", value_text: receipt.effective_stop_at },
      ]} />}
    </Card>;
  }
  const list = data.list_result;
  if (!list) return null;
  return <Card title="订阅与自动扣款" labelledBy={id}>
    <p>有效签约 {list.active_count} 项，近期续费合计 {yuan(list.upcoming_total_fen)}。</p>
    <p className="sh-hint">这是查询时的记录；发起取消后，请以下方新的办理结果为准。</p>
    {([['active', '有效签约'], ['suspected', '疑似周期扣款'], ['cancelled', '已退订']] as const).map(([status, label]) =>
      <section key={status} aria-labelledby={id + status}>
        <h4 id={id + status}>{label}</h4>
        {list.items.filter((item) => item.status === status).length === 0 && <p className="sh-hint">暂无项目</p>}
        {list.items.filter((item) => item.status === status).map((item) => <div className="sh-business-row" key={item.subscription_id}>
          <h5>{item.merchant_name} · {item.service_name}</h5>
          <FieldList fields={[
            { name: "amount", label: item.cycle === "monthly" ? "每月金额" : "每年金额", value_text: yuan(item.amount_fen) },
            { name: "account", label: "扣款账户", value_text: item.account_masked },
            ...(item.next_billing_at ? [{ name: "next", label: "下次扣款", value_text: item.next_billing_at }] : []),
          ]} />
          {status === "suspected" && <p className="sh-hint">根据流水发现的线索，尚未确认银行签约。{item.external_cancel_guide}</p>}
          {enabled && item.status === "active" && item.source_type === "mandate" && item.can_cancel_in_bank &&
            <ActionButton label={"取消「" + item.service_name + "」"} busy={busy}
              selection={{ action: "subscription_cancel", subscription_id: item.subscription_id }} onAction={onAction} />}
        </div>)}
      </section>)}
    {list.suspected_scan_status === "insufficient_data" && <p className="sh-hint">流水资料不足，疑似周期扣款尚未完整核对。</p>}
    <p className="sh-hint">查询时间：{list.as_of}</p>
  </Card>;
}

const CATEGORY_LABEL: Record<SpendingSummary["categories"][number]["category"], string> = {
  dining: "餐饮", transport: "交通", medical: "医疗", shopping: "购物", housing: "居住", transfer: "转账", other: "其他",
};

export function BillCardActions({ task, busy, onAction }: {
  task: ShellTask; busy: boolean; onAction: (selection: CardSelection) => Promise<string | null>;
}) {
  if (task.status !== "succeeded" || !task.data || typeof task.data !== "object") return null;
  const data = task.data;
  const summary = "report_id" in data ? (data as BillReport).summary : data as SpendingSummary;
  if (!Array.isArray(summary?.categories)) return null;
  return <Card title="继续查看这份账单" labelledBy={"task-" + task.task_id + "-bill-actions"}>
    <p className="sh-hint">沿用这份账单的时间和账户范围。</p>
    <div className="sh-business-actions">
      {summary.categories.map((item) => <ActionButton key={item.category}
        label={"查看" + CATEGORY_LABEL[item.category] + "明细"} busy={busy}
        selection={{ action: "bill_details", category: item.category }} onAction={onAction} />)}
      <ActionButton label="核对陌生扣款" busy={busy} selection={{ action: "bill_check" }} onAction={onAction} />
    </div>
  </Card>;
}
