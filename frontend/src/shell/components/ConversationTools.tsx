import { useState } from "react";
import { ArrowLeftRight, ChevronRight, FolderOpen, ReceiptText, CalendarHeart } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DetailsDrawer } from "./DetailsDrawer";
import { SERVICES } from "./ServiceNav";

export function ConversationStarters({ disabled, onChoose }: { disabled: boolean; onChoose: (text: string) => void }) {
  const starters = [
    { label: "给家人转一笔钱", text: "我要转账", icon: ArrowLeftRight },
    { label: "看看这个月花了多少", text: "查看本月账单", icon: ReceiptText },
    { label: "帮我安排养老金", text: "帮我安排养老金", icon: CalendarHeart },
  ];
  return <div className="sh-starters" aria-label="选择您想办的事">
    {starters.map(({ label, text, icon: Icon }) => <Button key={label} variant="outline" disabled={disabled}
      onClick={() => onChoose(text)}><Icon aria-hidden="true" /><span>{label}</span><ChevronRight aria-hidden="true" /></Button>)}
  </div>;
}

export function ConversationTools({ disabled, onChoose }: { disabled: boolean; onChoose: (text: string) => void }) {
  const [open, setOpen] = useState(false);
  return <DetailsDrawer title="查资料、办事情" open={open} onOpenChange={setOpen}
    triggerLabel={<><FolderOpen aria-hidden="true" />查资料 / 办业务</>}>
    <p className="sh-hint">选一项，我来帮您查。当前办理会保留。</p>
    <div className="sh-tool-list">
      {SERVICES.map(({ label, text, icon: Icon }) => <Button key={label} variant="outline" disabled={disabled}
        onClick={() => { setOpen(false); onChoose(text); }}><Icon aria-hidden="true" />{label}<ChevronRight aria-hidden="true" /></Button>)}
      <Button variant="outline" disabled={disabled} onClick={() => { setOpen(false); onChoose("帮我安排养老金"); }}>
        <CalendarHeart aria-hidden="true" />生活安排<ChevronRight aria-hidden="true" />
      </Button>
    </div>
  </DetailsDrawer>;
}
