import { useEffect, useRef, useState } from "react";
import type { InteractionRequest } from "../../contracts";
import { DELIVERY_FIELD_REQUIRED, DELIVERY_REFILL_NOTE } from "../copy";
import type { DeliveryFields, DeliveryHandoff } from "../types";
import { Card, FieldList, ReadOnlyStamp, StatusBadge } from "./Primitives";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ChevronRight } from "lucide-react";

const EMPTY: DeliveryFields = { recipient_name: "", phone: "", address: "" };
// The labels are the approved field names and `missing` is the approved sentence
// for that field: a blank field says which one to fill rather than making wording
// up, and the input keeps its own required/invalid state next to it.
const FIELDS = [
  { name: "recipient_name", label: "收件人", missing: DELIVERY_FIELD_REQUIRED.recipient_name, inputMode: undefined },
  { name: "phone", label: "联系电话", missing: DELIVERY_FIELD_REQUIRED.phone, inputMode: "tel" as const },
  { name: "address", label: "详细地址", missing: DELIVERY_FIELD_REQUIRED.address, inputMode: undefined },
] as const;

/**
 * The birthday delivery step. Its raw text goes only to F36, so this card is
 * deliberately not the generic text box: three named fields and, after F36, only
 * the server's mask plus the reference. The original is dropped from this
 * component the moment F36 answers, so a reference that later dies returns to
 * empty boxes instead of showing the typed recipient, phone and address again.
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
  const [blank, setBlank] = useState<Partial<Record<keyof DeliveryFields, boolean>>>({});
  const inputs = useRef<Partial<Record<keyof DeliveryFields, HTMLInputElement | null>>>({});
  // Only the interaction that issued the reference may continue it.
  const pending = handoff && handoff.interaction_id === interaction.interaction_id ? handoff : null;
  useEffect(() => {
    if (!handoff) return;
    setFields(EMPTY);
    setBlank({});
  }, [handoff]);
  const change = (name: keyof DeliveryFields, value: string) => {
    setFields((current) => ({ ...current, [name]: value }));
    setBlank((current) => ({ ...current, [name]: false }));
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
            <ChevronRight aria-hidden="true" />
          </button>
        ))}
        {pending ? (
          <div>
            <FieldList fields={pending.fields} />
            {error && <p role="alert" className="sh-inline-error">{error}</p>}
            <Button type="button" disabled={busy}
              onClick={() => void onContinue()}>{busy ? "正在继续…" : "用这些资料继续"}</Button>
          </div>
        ) : (
          <form className="sh-modify" autoComplete="off" onSubmit={(event) => {
            event.preventDefault();
            if (busy) return;
            const empty = FIELDS.filter((field) => !fields[field.name].trim());
            setBlank(Object.fromEntries(empty.map((field) => [field.name, true])));
            if (empty.length > 0) {
              inputs.current[empty[0].name]?.focus();
              return;
            }
            void onSubmit({
              recipient_name: fields.recipient_name.trim(),
              phone: fields.phone.trim(),
              address: fields.address.trim(),
            });
          }}>
            {/* Above the boxes, so it is read before anything is re-typed. */}
            <p className="sh-hint">{DELIVERY_REFILL_NOTE}</p>
            {FIELDS.map((field) => (
              <div key={field.name}>
                <label htmlFor={id + "-" + field.name}>{field.label}</label>
                <Input id={id + "-" + field.name} value={fields[field.name]}
                  ref={(element) => { inputs.current[field.name] = element; }}
                  onChange={(event) => change(field.name, event.target.value)}
                  inputMode={field.inputMode} aria-required="true" aria-invalid={Boolean(blank[field.name])}
                  aria-describedby={blank[field.name] ? id + "-" + field.name + "-error" : undefined}
                  autoComplete="off" disabled={busy} />
                {blank[field.name] && (
                  <p role="alert" id={id + "-" + field.name + "-error"} className="sh-inline-error">{field.missing}</p>
                )}
              </div>
            ))}
            {error && <p role="alert" className="sh-inline-error">{error}</p>}
            <Button type="submit" disabled={busy}>{busy ? "正在保存…" : "配送资料填好了，继续选商品"}</Button>
          </form>
        )}
      </div>
    </Card>
  );
}
