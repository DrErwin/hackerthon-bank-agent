import { useState } from "react";
import type { InteractionRequest } from "../../contracts";
import type { DeliveryFields, DeliveryHandoff } from "../types";
import { Card, FieldList, ReadOnlyStamp, StatusBadge } from "./Primitives";

const EMPTY: DeliveryFields = { recipient_name: "", phone: "", address: "" };
const FIELDS = [
  { name: "recipient_name", label: "收件人", missing: "请填写收件人姓名。", inputMode: undefined },
  { name: "phone", label: "联系电话", missing: "请填写联系电话。", inputMode: "tel" as const },
  { name: "address", label: "详细地址", missing: "请填写详细地址。", inputMode: undefined },
] as const;

/**
 * The birthday delivery step. Its raw text goes only to F36, so this card is
 * deliberately not the generic text box: three named fields, errors next to the
 * field that is wrong, and after F36 only the server's mask plus the reference.
 */
export function DeliveryCard({ interaction, active, busy, handoff, error, onSelect, onSubmit, onContinue, id }: {
  interaction: InteractionRequest;
  active: boolean;
  busy: boolean;
  handoff: DeliveryHandoff | null;
  error: string;
  onSelect: (optionId: string, label: string) => void;
  onSubmit: (fields: DeliveryFields) => Promise<boolean>;
  onContinue: () => Promise<boolean>;
  id: string;
}) {
  const [fields, setFields] = useState<DeliveryFields>(EMPTY);
  const [missing, setMissing] = useState<Partial<Record<keyof DeliveryFields, string>>>({});
  const change = (name: keyof DeliveryFields, value: string) => {
    setFields((current) => ({ ...current, [name]: value }));
    setMissing((current) => ({ ...current, [name]: undefined }));
  };
  if (!active) {
    return (
      <Card title={interaction.prompt} labelledBy={id} readOnly badge={<ReadOnlyStamp text="已结束" />}>
        <p className="sh-readonly-line">这一步已经结束。</p>
      </Card>
    );
  }
  return (
    <Card title={interaction.prompt} labelledBy={id} highlight badge={<StatusBadge tone="pending" icon="✎" text="等您补充" />}>
      <div className="sh-choices">
        {interaction.options.map((option) => (
          <button key={option.id} type="button" className="sh-choice" disabled={busy}
            onClick={() => onSelect(option.id, option.label)}>
            <span>{option.label}</span>
            <span aria-hidden="true">›</span>
          </button>
        ))}
        {handoff ? (
          <div>
            <FieldList fields={handoff.fields} />
            {error && <p role="alert" className="sh-inline-error">{error}</p>}
            <button type="button" className="sh-btn sh-btn-primary" disabled={busy}
              onClick={() => void onContinue()}>资料不用再填，点下面继续</button>
          </div>
        ) : (
          <form className="sh-modify" autoComplete="off" onSubmit={(event) => {
            event.preventDefault();
            if (busy) return;
            const empty = Object.fromEntries(FIELDS
              .filter((field) => !fields[field.name].trim())
              .map((field) => [field.name, field.missing])) as Partial<Record<keyof DeliveryFields, string>>;
            setMissing(empty);
            if (Object.keys(empty).length > 0) return;
            void onSubmit({
              recipient_name: fields.recipient_name.trim(),
              phone: fields.phone.trim(),
              address: fields.address.trim(),
            }).then((saved) => { if (saved) setFields(EMPTY); });
          }}>
            {FIELDS.map((field) => (
              <div key={field.name}>
                <label htmlFor={id + "-" + field.name}>{field.label}</label>
                <input id={id + "-" + field.name} value={fields[field.name]}
                  onChange={(event) => change(field.name, event.target.value)}
                  inputMode={field.inputMode} aria-invalid={Boolean(missing[field.name])}
                  aria-describedby={missing[field.name] ? id + "-" + field.name + "-error" : undefined}
                  autoComplete="off" disabled={busy} />
                {missing[field.name] && (
                  <p role="alert" id={id + "-" + field.name + "-error"} className="sh-inline-error">{missing[field.name]}</p>
                )}
              </div>
            ))}
            {error && <p role="alert" className="sh-inline-error">{error}</p>}
            <button type="submit" className="sh-btn sh-btn-primary" disabled={busy}>配送资料填好了，继续选商品</button>
          </form>
        )}
      </div>
    </Card>
  );
}
