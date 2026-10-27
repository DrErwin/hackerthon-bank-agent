import { useRef, useState } from "react";
import type { InteractionRequest } from "../../contracts";
import type { DataOrigin, DisplayField, ReportView, ResultView } from "../types";
import { Card, FieldList, OriginTag, ReadOnlyStamp, Spinner, StatusBadge } from "./Primitives";
import { DetailsDrawer } from "./DetailsDrawer";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChevronRight, CircleCheck, CircleAlert, CircleX, Clock3 } from "lucide-react";

const RESULT_ICON: Record<ResultView["tone"], string> = { success: "✓", danger: "✕", warning: "!", pending: "…", neutral: "−" };

export function WaitingCard({ message, facts, id }: { message: string; facts: DisplayField[]; id: string }) {
  return (
    <Card title="正在办理" labelledBy={id} highlight badge={<StatusBadge tone="pending" icon="…" text="处理中" />}>
      <div className="sh-progress" role="status" aria-live="polite">
        <Spinner />
        <span>{message}</span>
      </div>
      <Progress value={null} aria-label="办理进度" />
      <FieldList fields={facts} />
    </Card>
  );
}

export function InputCard({ interaction, active, busy, selectedLabel, onSelect, onSubmitText, textLabel, numeric = false, id }: {
  interaction: InteractionRequest;
  active: boolean;
  busy: boolean;
  selectedLabel: string | null;
  onSelect: (optionId: string, label: string) => void;
  onSubmitText?: (text: string) => Promise<boolean>;
  // Cross-linkage menus ask for values (an amount, a date, a controlled
  // reference) with the same selection interaction; the answer is typed.
  textLabel?: string;
  // A typed quantity is a positive integer; the hint is the server's own prompt
  // and the server still refuses every value it does not accept.
  numeric?: boolean;
  id: string;
}) {
  const [text, setText] = useState("");
  const [quantityError, setQuantityError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const field = interaction.required_fields.length === 1 ? interaction.required_fields[0] : "";
  const labels: Record<string, string> = {
    amount_fen: "转账金额（元）", payee_hint: "收款人姓名或备注",
    payer_account_id: "付款账户编号", merchant_hint: "商户名称",
  };
  const inputLabel = labels[field];
  const typingLabel = inputLabel ?? textLabel;
  const typed = text.trim();
  const ready = Boolean(typed) && (!numeric || /^[1-9]\d*$/.test(typed));
  return (
    <Card
      title={interaction.prompt}
      labelledBy={id}
      readOnly={!active}
      highlight={active}
      badge={active ? <StatusBadge tone="pending" icon="✎" text={typingLabel ? "等您补充" : "等您选择"} /> : <ReadOnlyStamp text={selectedLabel ? "已选择" : "已结束"} />}
    >
      {active ? (
        <div className="sh-choices">
          {interaction.options.map((option) => (
            <button key={option.id} type="button" className="sh-choice" disabled={busy} onClick={() => onSelect(option.id, option.label)}>
              <span>{option.label}</span>
              <ChevronRight aria-hidden="true" />
            </button>
          ))}
          {typingLabel && onSubmitText && (
            <form className="sh-modify" onSubmit={async (event) => {
              event.preventDefault();
              if (busy) return;
              if (!ready) {
                if (numeric) { setQuantityError(true); inputRef.current?.focus(); }
                return;
              }
              if (await onSubmitText(text)) setText("");
            }}>
              <label htmlFor={id + "-input"}>{typingLabel}</label>
              <Input ref={inputRef} id={id + "-input"} value={text} onChange={(event) => { setText(event.target.value); setQuantityError(false); }}
                aria-invalid={quantityError} aria-describedby={quantityError ? id + "-error" : undefined}
                inputMode={numeric ? "numeric" : field === "amount_fen" ? "decimal" : "text"} autoComplete="off" disabled={busy} required />
              {quantityError && <p id={id + "-error"} role="alert" className="sh-inline-error">数量要填大于零的整数，例如 2。</p>}
              <Button disabled={busy || (!numeric && !ready)}>{busy ? "正在更新…" : textLabel ? "填好了，继续" : "补充并继续"}</Button>
            </form>
          )}
          {typingLabel && <p className="sh-hint">也可以在下方对话框里告诉我。</p>}
        </div>
      ) : (
        <p className="sh-readonly-line">{selectedLabel ? "您选择了：" + selectedLabel : "这一步已经结束。"}</p>
      )}
    </Card>
  );
}

export function ResultCard({ view, origin, id }: { view: ResultView; origin: DataOrigin; id: string }) {
  const primary = view.fields.filter((field) => !field.name.endsWith("-ids") && field.name !== "transaction");
  const references = view.fields.filter((field) => !primary.includes(field));
  const Icon = view.tone === "success" ? CircleCheck : view.tone === "danger" ? CircleX : view.tone === "pending" ? Clock3 : CircleAlert;
  return (
    <Card title="办理结果" labelledBy={id} className={"sh-result sh-result-" + view.tone} badge={<StatusBadge tone={view.tone} icon={RESULT_ICON[view.tone]} text={view.title} />}>
      <Icon className="sh-result-symbol" aria-hidden="true" />
      {view.headline && <p className="sh-headline">{view.headline}</p>}
      <FieldList fields={primary} />
      {references.length > 0 && <DetailsDrawer title="办理凭证"><FieldList fields={references} /></DetailsDrawer>}
      {view.note && <p className="sh-hint">{view.note}</p>}
      {origin !== "real-api" && <p className="sh-demo-note"><OriginTag origin={origin} /> 示例回执</p>}
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
        <Button type="button" disabled={busy} onClick={onQuery}>
          {busy ? "正在查询…" : "查询原操作"}
        </Button>
      ) : (
        <p className="sh-hint">请按上面的提示处理。</p>
      )}
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
      badge={resolved ? undefined : <StatusBadge tone="warning" icon="↺" text="待您查看" />}
    >
      {resolved ? (
        <p className="sh-readonly-line">{resolvedText ?? "已找回上次的办理资料，请查看当前进度。"}</p>
      ) : (
        <>
          <p className="sh-lead">办理资料已保留，先查看最新进度。</p>
          <FieldList fields={[...facts, { name: "status", label: "当时状态", value_text: statusText }]} />
          {reason && <p className="sh-hint">{reason}</p>}
          <div className="sh-actions">
            <Button type="button" disabled={busy} onClick={onResume}>
              {busy ? "正在恢复…" : "查看原任务"}
            </Button>
            {canDiscard && (
              <Button type="button" variant="outline" disabled={busy} onClick={onDiscard}>放弃这次任务</Button>
            )}
          </div>
        </>
      )}
    </Card>
  );
}
