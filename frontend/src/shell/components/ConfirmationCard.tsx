import type { ConfirmationView, InteractionOption } from "../../contracts";
import { EDIT_OPTION_NOTE } from "../copy";
import { clockTime } from "../format";
import type { SlotAction } from "../slots";
import { Card, FieldList, ReadOnlyStamp, StatusBadge } from "./Primitives";
import { Button } from "@/components/ui/button";
import { ShieldCheck } from "lucide-react";

const DECISION_TEXT: Record<ConfirmationView["decision"], string> = {
  pending: "未作答",
  approved: "已确认办理",
  cancelled: "已取消",
  expired: "已过期",
  superseded: "已被新确认单替代",
};

export function ConfirmationCard({ view, title, emphasize, active, canConfirm, canCancel, busy, extraActions, options, onSelectOption, onAnswer, confirmLabel = "确认办理", cancelLabel = "取消", id }: {
  view: ConfirmationView;
  title: string;
  emphasize?: string;
  // Business wording for the two answers; the answers themselves never change.
  confirmLabel?: string;
  cancelLabel?: string;
  active: boolean;
  canConfirm: boolean;
  canCancel: boolean;
  busy: boolean;
  extraActions: SlotAction[];
  // Options published by the backend on this card (the birthday controlled edit).
  // They are answered by option id through F10, never by matching their label.
  options?: InteractionOption[];
  onSelectOption?: (optionId: string, label: string) => void;
  onAnswer: (choice: "approve" | "cancel") => void;
  id: string;
}) {
  const live = active && view.decision === "pending";
  // The gate publishes these two reserved IDs as well. They use the dedicated
  // confirmation endpoint above, while additional options keep the F10 route.
  const editOptions = (options ?? []).filter((option) => option.id !== "approve" && option.id !== "cancel");
  return (
    <Card
      title={live ? title : "确认单记录"}
      labelledBy={id}
      readOnly={!live}
      highlight={live}
      className="sh-confirmation"
      badge={live ? <StatusBadge tone="pending" icon="?" text="等您确认" /> : <ReadOnlyStamp text={DECISION_TEXT[view.decision]} />}
    >
      <FieldList fields={view.display_fields} emphasize={emphasize} />
      {live ? (
        <>
          <p className="sh-hint">核对好后，请点「{confirmLabel}」。这份确认单在 {clockTime(view.expires_at)} 前有效。</p>
          <div className="sh-actions">
            {canConfirm && (
              <Button type="button" disabled={busy} onClick={() => onAnswer("approve")}>
                <ShieldCheck aria-hidden="true" />
                {busy ? "正在提交…" : confirmLabel}
              </Button>
            )}
            {extraActions.map((action) => (
              <button key={action.label} type="button" className="sh-btn sh-btn-secondary" disabled={busy} onClick={action.onClick}>{action.label}</button>
            ))}
            {editOptions.map((option) => (
              <button key={option.id} type="button" className="sh-btn sh-btn-secondary" disabled={busy}
                onClick={() => onSelectOption?.(option.id, option.label)}>{option.label}</button>
            ))}
            {canCancel && (
              <Button type="button" variant="outline" disabled={busy} onClick={() => onAnswer("cancel")}>{cancelLabel}</Button>
            )}
          </div>
          {/* The page never matches an option by its label, so "the server published
              options" is the only condition it can test for the edit explanation. */}
          {editOptions.length > 0 && <p className="sh-hint">{EDIT_OPTION_NOTE}</p>}
        </>
      ) : (
        <p className="sh-readonly-line">这份确认记录已保存，供您回看。</p>
      )}
    </Card>
  );
}
