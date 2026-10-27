import { useRef, useState } from "react";
import { ArrowLeftRight, ChevronDown, ChevronUp, CreditCard, LayoutGrid, ReceiptText, Repeat2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";

export const SERVICES = [
  { label: "我要转账", text: "我要转账", icon: ArrowLeftRight },
  { label: "我的账户", text: "我有哪些账户和余额", icon: CreditCard },
  { label: "我的收款人", text: "我有哪些收款人", icon: Users },
  { label: "查看账单", text: "查看本月账单", icon: ReceiptText },
  { label: "自动扣费", text: "查看我的订阅和自动扣费", icon: Repeat2 },
];

export function ServiceNav({ disabled, onChoose }: { disabled: boolean; onChoose: (text: string) => void }) {
  const [expanded, setExpanded] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  return <nav className="sh-service-nav" aria-label="常用服务">
    <Button ref={toggle} type="button" variant="ghost" size="sm" className="sh-service-toggle" aria-expanded={expanded}
      aria-controls="sh-service-list" onClick={() => setExpanded(!expanded)}>
      <LayoutGrid aria-hidden="true" />常用服务{expanded ? <ChevronUp aria-hidden="true" /> : <ChevronDown aria-hidden="true" />}
    </Button>
    <div id="sh-service-list" className={"sh-service-list" + (expanded ? " is-open" : "")}>
      {SERVICES.map(({ label, text, icon: Icon }) => <Button type="button" variant="outline" size="sm" key={label}
        disabled={disabled} onClick={() => {
          setExpanded(false);
          if (window.innerWidth < 960) toggle.current?.focus();
          onChoose(text);
        }}><Icon aria-hidden="true" />{label}</Button>)}
    </div>
  </nav>;
}
