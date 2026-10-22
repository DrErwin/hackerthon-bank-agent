import { useState } from "react";
import type { InteractionRequest } from "../../contracts";
import type { DataOrigin, DisplayField, ReportView, ResultView } from "../types";
import { Card, FieldList, OriginTag, ReadOnlyStamp, Spinner, StatusBadge } from "./Primitives";
import { DetailsDrawer } from "./DetailsDrawer";

const RESULT_ICON: Record<ResultView["tone"], string> = { success: "✓", danger: "✕", warning: "!", pending: "…", neutral: "−" };

export function WaitingCard({ message, facts, id }: { message: string; facts: DisplayField[]; id: string }) {
  return (
    <Card title="正在办理，请不要重复操作" labelledBy={id} highlight badge={<StatusBadge tone="pending" icon="…" text="处理中" />}>
      <div className="sh-progress" role="status" aria-live="polite">
        <Spinner />
        <span>{message}</span>
      </div>
      <FieldList fields={facts} />
    </Card>
  );
}

export function InputCard({ interaction, active, busy, selectedLabel, onSelect, onSubmitText, id }: {
  interaction: InteractionRequest;
  active: boolean;
  busy: boolean;
  selectedLabel: string | null;
  onSelect: (optionId: string, label: string) => void;
  onSubmitText?: (text: string) => Promise<boolean>;
  id: string;
}) {
  const [text, setText] = useState("");
  const field = interaction.required_fields.length === 1 ? interaction.required_fields[0] : "";
  const labels: Record<string, string> = {
    amount_fen: "转账金额（元）", payee_hint: "收款人姓名或备注",
    payer_account_id: "付款账户编号", merchant_hint: "商户名称",
  };
  const inputLabel = labels[field];
  return (
    <Card
      title={interaction.prompt}
      labelledBy={id}
      readOnly={!active}
      highlight={active}
      badge={active ? <StatusBadge tone="pending" icon="✎" text={inputLabel ? "等您补充" : "等您选择"} /> : <ReadOnlyStamp text={selectedLabel ? "已选择" : "已结束"} />}
    >
      {active ? (
        <div className="sh-choices">
          {interaction.options.map((option) => (
            <button key={option.id} type="button" className="sh-choice" disabled={busy} onClick={() => onSelect(option.id, option.label)}>
              <span>{option.label}</span>
              <span aria-hidden="true">›</span>
            </button>
          ))}
          {inputLabel && onSubmitText && (
            <form className="sh-modify" onSubmit={async (event) => {
              event.preventDefault();
              if (!text.trim() || busy) return;
              if (await onSubmitText(text)) setText("");
            }}>
              <label htmlFor={id + "-input"}>{inputLabel}</label>
              <input id={id + "-input"} value={text} onChange={(event) => setText(event.target.value)}
                inputMode={field === "amount_fen" ? "decimal" : "text"} autoComplete="off" disabled={busy} required />
              <button className="sh-btn sh-btn-primary" disabled={busy || !text.trim()}>补充并继续</button>
            </form>
          )}
          <p className="sh-hint">{inputLabel ? "填写后继续这项办理，不会另起一笔。" : "请自己点选，系统不会替您默认选择。"}</p>
        </div>
      ) : (
        <p className="sh-readonly-line">{selectedLabel ? "您选择了：" + selectedLabel : "这一步已经结束。"}</p>
      )}
    </Card>
  );
}

export function ResultCard({ view, origin, id }: { view: ResultView; origin: DataOrigin; id: string }) {
  const important = view.tone === "warning" || view.tone === "danger";
  const primary = important ? view.fields.filter((field) => !field.name.endsWith("-ids")) : view.fields.slice(0, 3);
  return (
    <Card title="办理结果" labelledBy={id} badge={<StatusBadge tone={view.tone} icon={RESULT_ICON[view.tone]} text={view.title} />}>
      {view.headline && <p className="sh-headline">{view.headline}</p>}
      <FieldList fields={primary} />
      {primary.length < view.fields.length &&
        <DetailsDrawer title={"查看全部明细（" + view.fields.length + "项）"}><FieldList fields={view.fields} /></DetailsDrawer>}
      {view.note && <p className="sh-hint">{view.note}</p>}
      {origin !== "real-api" && <p className="sh-demo-note"><OriginTag origin={origin} /> 演示结果，不代表真实银行交易。</p>}
    </Card>
  );
}

export function ReportCard({ view, origin, id }: { view: ReportView; origin: DataOrigin; id: string }) {
  return (
    <Card title={view.title} labelledBy={id} badge={<StatusBadge tone="neutral" icon="▤" text="报告" />}>
      <p className="sh-hint">统计范围：{view.periodLabel}</p>
      {view.headline && (
        <div className="sh-report-headline">
          <span>{view.headline.label}</span>
          <strong>{view.headline.value}</strong>
        </div>
      )}
      <FieldList fields={view.fields} />
      {view.note && <p className="sh-hint">{view.note}</p>}
      {origin !== "real-api" && <p className="sh-demo-note"><OriginTag origin={origin} /> 演示数据，不代表真实账单。</p>}
    </Card>
  );
}

export function NeedsAttentionCard({ facts, message, canQuery, busy, onQuery, id }: {
  facts: DisplayField[];
  message: string;
  canQuery: boolean;
  busy: boolean;
  onQuery: () => void;
  id: string;
}) {
  return (
    <Card title={canQuery ? "结果还在核实" : "这项办理暂时停下了"} labelledBy={id} highlight badge={<StatusBadge tone="warning" icon="!" text="请留意" />}>
      {canQuery && <p className="sh-lead">结果还没查清，请先查看原来那笔。</p>}
      {message && <p className="sh-hint">{message}</p>}
      <FieldList fields={facts} />
      {canQuery ? (
        <button type="button" className="sh-btn sh-btn-primary" disabled={busy} onClick={onQuery}>
          {busy ? "正在查询…" : "查询原操作"}
        </button>
      ) : (
        <p className="sh-hint">请按上面的提示处理。</p>
      )}
      {canQuery && <p className="sh-hint">查询不会再办一次。</p>}
    </Card>
  );
}

export function RecoveryCard({ facts, statusText, reason, resolved, resolvedText, canDiscard, busy, onResume, onDiscard, id }: {
  facts: DisplayField[];
  statusText: string;
  reason: string | null;
  resolved: boolean;
  resolvedText?: string;
  canDiscard: boolean;
  busy: boolean;
  onResume: () => void;
  onDiscard: () => void;
  id: string;
}) {
  return (
    <Card
      title={resolved ? "已找回这项办理" : "这项还没办完"}
      labelledBy={id}
      readOnly={resolved}
      highlight={!resolved}
      badge={resolved ? <ReadOnlyStamp text="已处理" /> : <StatusBadge tone="warning" icon="↺" text="待您查看" />}
    >
      {resolved ? (
        <p className="sh-readonly-line">{resolvedText ?? "已恢复原任务，没有创建新任务，也没有重新提交。"}</p>
      ) : (
        <>
          <p className="sh-lead">要接着办吗？先查看上次的内容，再由您决定。</p>
          <FieldList fields={[...facts, { name: "status", label: "当时状态", value_text: statusText }]} />
          {reason && <p className="sh-hint">{reason}</p>}
          <div className="sh-actions">
            <button type="button" className="sh-btn sh-btn-primary" disabled={busy} onClick={onResume}>
              {busy ? "正在恢复…" : "查看原任务"}
            </button>
            {canDiscard && (
              <button type="button" className="sh-btn sh-btn-secondary" disabled={busy} onClick={onDiscard}>放弃这次任务</button>
            )}
          </div>
        </>
      )}
    </Card>
  );
}
