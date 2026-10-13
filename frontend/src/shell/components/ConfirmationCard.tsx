import type { ConfirmationView } from "../../contracts";
import { clockTime } from "../format";
import type { SlotAction } from "../slots";
import { Card, FieldList, ReadOnlyStamp, StatusBadge } from "./Primitives";

const DECISION_TEXT: Record<ConfirmationView["decision"], string> = {
  pending: "未作答",
  approved: "已确认办理",
  cancelled: "已取消",
  expired: "已过期",
  superseded: "已被新确认单替代",
};

export function ConfirmationCard({ view, title, emphasize, active, canConfirm, canCancel, busy, extraActions, onAnswer, id }: {
  view: ConfirmationView;
  title: string;
  emphasize?: string;
  active: boolean;
  canConfirm: boolean;
  canCancel: boolean;
  busy: boolean;
  extraActions: SlotAction[];
  onAnswer: (choice: "approve" | "cancel") => void;
  id: string;
}) {
  const live = active && view.decision === "pending";
  return (
    <Card
      title={live ? title : "确认单记录"}
      labelledBy={id}
      readOnly={!live}
      highlight={live}
      badge={live ? <StatusBadge tone="pending" icon="?" text="等您确认" /> : <ReadOnlyStamp text={DECISION_TEXT[view.decision]} />}
    >
      <FieldList fields={view.display_fields} emphasize={emphasize} />
      {live ? (
        <>
          <p className="sh-hint">请逐项核对。在聊天里说「确认」不算数，必须点下面的按钮。确认单在 {clockTime(view.expires_at)} 前有效。</p>
          <div className="sh-actions">
            {canConfirm && (
              <button type="button" className="sh-btn sh-btn-primary" disabled={busy} onClick={() => onAnswer("approve")}>
                {busy ? "正在提交…" : "确认办理"}
              </button>
            )}
            {extraActions.map((action) => (
              <button key={action.label} type="button" className="sh-btn sh-btn-secondary" disabled={busy} onClick={action.onClick}>{action.label}</button>
            ))}
            {canCancel && (
              <button type="button" className="sh-btn sh-btn-secondary" disabled={busy} onClick={() => onAnswer("cancel")}>取消</button>
            )}
          </div>
        </>
      ) : (
        <p className="sh-readonly-line">这张确认单已转为只读，保留在记录里供您核对，按钮不能再点。</p>
      )}
    </Card>
  );
}
