import type { InteractionRequest } from "../../contracts";
import type { DataOrigin, DisplayField, ReportView, ResultView } from "../types";
import { Card, FieldList, OriginTag, ReadOnlyStamp, Spinner, StatusBadge } from "./Primitives";

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

export function InputCard({ interaction, active, busy, selectedLabel, onSelect, id }: {
  interaction: InteractionRequest;
  active: boolean;
  busy: boolean;
  selectedLabel: string | null;
  onSelect: (optionId: string, label: string) => void;
  id: string;
}) {
  return (
    <Card
      title={interaction.prompt}
      labelledBy={id}
      readOnly={!active}
      highlight={active}
      badge={active ? <StatusBadge tone="pending" icon="✎" text="等您选择" /> : <ReadOnlyStamp text={selectedLabel ? "已选择" : "已结束"} />}
    >
      {active ? (
        <div className="sh-choices">
          {interaction.options.map((option) => (
            <button key={option.id} type="button" className="sh-choice" disabled={busy} onClick={() => onSelect(option.id, option.label)}>
              <span>{option.label}</span>
              <span aria-hidden="true">›</span>
            </button>
          ))}
          <p className="sh-hint">请自己点选，系统不会替您默认选择。</p>
        </div>
      ) : (
        <p className="sh-readonly-line">{selectedLabel ? "您选择了：" + selectedLabel : "这一步已经结束。"}</p>
      )}
    </Card>
  );
}

export function ResultCard({ view, origin, id }: { view: ResultView; origin: DataOrigin; id: string }) {
  return (
    <Card title="办理结果" labelledBy={id} badge={<StatusBadge tone={view.tone} icon={RESULT_ICON[view.tone]} text={view.title} />}>
      {view.headline && <p className="sh-headline">{view.headline}</p>}
      <FieldList fields={view.fields} />
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
    <Card title="结果还在核实" labelledBy={id} highlight badge={<StatusBadge tone="warning" icon="!" text="结果待核实" />}>
      <p className="sh-lead">这笔办理的结果我暂时没查到，我没有再提交一次。</p>
      {message && <p className="sh-hint">{message}</p>}
      <FieldList fields={facts} />
      {canQuery ? (
        <button type="button" className="sh-btn sh-btn-primary" disabled={busy} onClick={onQuery}>
          {busy ? "正在查询…" : "查询原操作"}
        </button>
      ) : (
        <p className="sh-hint">暂时不能查询，请稍后刷新状态。</p>
      )}
      <p className="sh-hint">查询只看原来那笔的结果，不会重新提交。</p>
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
      title={resolved ? "刷新前的任务" : "有一项没办完的任务"}
      labelledBy={id}
      readOnly={resolved}
      highlight={!resolved}
      badge={resolved ? <ReadOnlyStamp text="已处理" /> : <StatusBadge tone="warning" icon="↺" text="待您查看" />}
    >
      {resolved ? (
        <p className="sh-readonly-line">{resolvedText ?? "已恢复原任务，没有创建新任务，也没有重新提交。"}</p>
      ) : (
        <>
          <p className="sh-lead">页面刷新或重新进入前，这项任务还没办完。为避免重复操作，我不会自动继续。</p>
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
