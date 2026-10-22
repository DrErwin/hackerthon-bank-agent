import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

export function DetailsDrawer({ title, children }: { title: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal();
  }, [open]);
  return <>
    <button type="button" className="sh-link-btn" ref={trigger} onClick={() => setOpen(true)}>{title}</button>
    {open && createPortal(<dialog ref={dialog} className="sh-root sh-detail-drawer" aria-label={title}
      onClose={() => { setOpen(false); trigger.current?.focus(); }}
      onClick={(event) => { if (event.target === event.currentTarget) dialog.current?.close(); }}>
      <div className="sh-drawer-panel">
        <header><h2>{title}</h2><button type="button" className="sh-btn sh-btn-secondary" autoFocus onClick={() => dialog.current?.close()}>关闭详情</button></header>
        <div className="sh-drawer-body">{children}</div>
      </div>
    </dialog>, document.body)}
  </>;
}
