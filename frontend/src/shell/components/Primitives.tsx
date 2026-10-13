import type { ReactNode } from "react";
import { originLabel } from "../format";
import type { DataOrigin, DisplayField, Tone } from "../types";

export function StatusBadge({ tone, icon, text }: { tone: Tone; icon: string; text: string }) {
  return (
    <span className={"sh-badge sh-tone-" + tone}>
      <span className="sh-badge-icon" aria-hidden="true">{icon}</span>
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
  const icon = tone === "danger" ? "✕" : tone === "warning" ? "!" : "i";
  return (
    <div className={"sh-notice sh-notice-" + tone} role={tone === "info" ? "status" : "alert"}>
      <span className="sh-notice-icon" aria-hidden="true">{icon}</span>
      <div className="sh-notice-body">
        <strong>{title}</strong>
        {children && <div className="sh-notice-text">{children}</div>}
        {action}
      </div>
    </div>
  );
}

export function Card({ title, badge, readOnly, highlight, children, footer, labelledBy }: {
  title: string;
  badge?: ReactNode;
  readOnly?: boolean;
  highlight?: boolean;
  children?: ReactNode;
  footer?: ReactNode;
  labelledBy?: string;
}) {
  const className = "sh-card" + (readOnly ? " sh-card-readonly" : "") + (highlight ? " sh-card-highlight" : "");
  return (
    <section className={className} aria-labelledby={labelledBy}>
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
  return <span className="sh-stamp">{text} · 只读</span>;
}

export function Spinner() {
  return <span className="sh-spinner" aria-hidden="true" />;
}
