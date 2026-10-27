import type { ReactNode } from "react";
import { CircleAlert, CircleCheck, CircleMinus, CircleX, Clock3, Info, LoaderCircle } from "lucide-react";
import { originLabel } from "../format";
import type { DataOrigin, DisplayField, Tone } from "../types";

export function StatusBadge({ tone, icon, text }: { tone: Tone; icon: string; text: string }) {
  const Icon = { success: CircleCheck, danger: CircleX, warning: CircleAlert, pending: Clock3, neutral: CircleMinus }[tone];
  return (
    <span className={"sh-badge sh-tone-" + tone}>
      <Icon className="sh-badge-icon" aria-hidden="true" data-status-icon={icon} />
      {text}
    </span>
  );
}

export function FieldList({ fields, emphasize }: { fields: DisplayField[]; emphasize?: string }) {
  if (fields.length === 0) return null;
  return (
    <dl className="sh-fields">
      {fields.map((field) => (
        <div className={"sh-field" + (field.name === emphasize ? " sh-field-emphasis" : "")} key={field.name}>
          <dt>{field.label}</dt>
          <dd>{field.value_text}</dd>
        </div>
      ))}
    </dl>
  );
}

export function OriginTag({ origin }: { origin: DataOrigin }) {
  const label = originLabel(origin);
  if (!label) return null;
  return <span className="sh-origin-tag">{label}</span>;
}

export function Notice({ tone, title, children, action }: { tone: "danger" | "warning" | "info"; title: string; children?: ReactNode; action?: ReactNode }) {
  const Icon = tone === "danger" ? CircleX : tone === "warning" ? CircleAlert : Info;
  return (
    <div className={"sh-notice sh-notice-" + tone} role={tone === "info" ? "status" : "alert"}>
      <Icon className="sh-notice-icon" aria-hidden="true" />
      <div className="sh-notice-body">
        <strong>{title}</strong>
        {children && <div className="sh-notice-text">{children}</div>}
        {action}
      </div>
    </div>
  );
}

export function Card({ title, badge, readOnly, highlight, children, footer, labelledBy, className = "" }: {
  title: string;
  badge?: ReactNode;
  readOnly?: boolean;
  highlight?: boolean;
  children?: ReactNode;
  footer?: ReactNode;
  labelledBy?: string;
  className?: string;
}) {
  const classes = "sh-card " + className + (readOnly ? " sh-card-readonly" : "") + (highlight ? " sh-card-highlight" : "");
  return (
    <section className={classes} aria-labelledby={labelledBy}>
      <header className="sh-card-head">
        <h3 id={labelledBy}>{title}</h3>
        {badge}
      </header>
      {children}
      {footer && <footer className="sh-card-foot">{footer}</footer>}
    </section>
  );
}

export function ReadOnlyStamp({ text }: { text: string }) {
  return <span className="sh-stamp">{text}</span>;
}

export function Spinner() {
  return <LoaderCircle className="sh-spinner" aria-hidden="true" />;
}
