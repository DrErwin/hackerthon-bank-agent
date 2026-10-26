import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, CircleCheck, CreditCard, Search, Type, Users } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Toaster } from "@/components/ui/sonner";
import { DetailsDrawer } from "./components/DetailsDrawer";
import { FieldList, Notice, Spinner } from "./components/Primitives";
import "./design-system-page.css";

const PEOPLE = [
  { name: "女儿", detail: "陈*宁 · 建设银行 · 尾号 8826" },
  { name: "老伴", detail: "李*华 · 工商银行 · 尾号 5610" },
  { name: "物业费", detail: "示例物业 · 农业银行 · 尾号 3902" },
];

export default function DesignSystemPage() {
  const [largeText, setLargeText] = useState(false);
  const [person, setPerson] = useState(PEOPLE[0]);
  const [search, setSearch] = useState("");
  const [amount, setAmount] = useState("300");
  const [error, setError] = useState("");
  const [review, setReview] = useState(false);
  const [status, setStatus] = useState<"waiting" | "unknown" | "empty">("waiting");
  const [loading, setLoading] = useState(false);
  const fields = [
    { name: "payee", label: "收款人", value_text: person.name },
    { name: "account", label: "收款账户", value_text: person.detail },
    { name: "payer", label: "付款银行卡", value_text: "工商银行 · 尾号 6218" },
    { name: "amount", label: "转账金额", value_text: `¥${Number(amount).toFixed(2)}` },
    { name: "fee", label: "手续费", value_text: "¥0.00" },
  ];
  return <div className="ds-page" data-text-size={largeText ? "large" : "standard"}>
    <header className="ds-header">
      <a href="/"><ArrowLeft aria-hidden="true" />银行助手</a>
      <Button type="button" variant="ghost" size="sm" aria-pressed={largeText} onClick={() => {
        setLargeText(!largeText); toast(largeText ? "已恢复标准字号" : "文字已放大");
      }}><Type aria-hidden="true" />{largeText ? "标准字" : "大字"}</Button>
    </header>
    <main className="ds-main">
      <div className="ds-intro"><h1>看得清，选得快，办得明白。</h1><p>设计系统 v0.2 · 下面是可点击的组件体验，资料为虚构示例。</p></div>
      <div className="ds-columns">
        <section className="ds-transfer" aria-labelledby="ds-transfer-title">
          <div className="ds-section-title"><h2 id="ds-transfer-title">{review ? "核对这笔转账" : "转给家人"}</h2><span>示例</span></div>
          <ol className="ds-steps" aria-label="转账步骤"><li className="is-done"><Check aria-hidden="true" />选收款人</li><li aria-current={review ? undefined : "step"}>填金额</li><li aria-current={review ? "step" : undefined}>核对</li></ol>
          {review ? <>
            <FieldList fields={fields} emphasize="amount" />
            <p className="ds-summary-note"><CircleCheck aria-hidden="true" />核对清单让每项资料都可以回看。</p>
            <Button variant="outline" onClick={() => setReview(false)}><ArrowLeft aria-hidden="true" />返回修改</Button>
          </> : <>
            <div className="ds-person"><span className="ds-person-icon"><Users aria-hidden="true" /></span><div><strong>{person.name}</strong><p>{person.detail}</p></div></div>
            <DetailsDrawer title="换一位收款人">
              <div className="ds-selector">
                <label htmlFor="ds-search"><Search aria-hidden="true" />查找收款人</label>
                <Input id="ds-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="输入备注、银行或尾号" />
                {PEOPLE.filter((item) => (item.name + item.detail).includes(search.trim())).map((item) => <Button variant="outline" className="ds-person-choice" key={item.name}
                  aria-pressed={item.name === person.name} onClick={() => setPerson(item)}>
                  <span><strong>{item.name}</strong><span>{item.detail}</span></span>{item.name === person.name && <Check aria-hidden="true" />}
                </Button>)}
                {!PEOPLE.some((item) => (item.name + item.detail).includes(search.trim())) && <p>换个备注或尾号试试。</p>}
                <p className="ds-selected" role="status">已选：{person.name}</p>
              </div>
            </DetailsDrawer>
            <form onSubmit={(event) => {
              event.preventDefault();
              if (!/^\d+(?:\.\d{1,2})?$/.test(amount) || Number(amount) <= 0) { setError("请填写大于零的金额，最多两位小数。"); return; }
              setReview(true);
            }}>
              <label htmlFor="ds-amount">转账金额（元）</label>
              <Input className="ds-amount" id="ds-amount" inputMode="decimal" value={amount} aria-invalid={Boolean(error)} aria-describedby={error ? "ds-amount-error" : undefined}
                onChange={(event) => { setAmount(event.target.value); setError(""); }} />
              {error && <p id="ds-amount-error" className="ds-error" role="alert">{error}</p>}
              <div className="ds-bank"><CreditCard aria-hidden="true" /><div><strong>工商银行 · 尾号 6218</strong><p>可用余额 ¥12,680.50</p></div></div>
              <Button className="ds-primary" type="submit">核对这笔转账<ArrowRight aria-hidden="true" /></Button>
            </form>
          </>}
          <DetailsDrawer title="查看费用和到账说明"><div className="ds-selector"><h3>这笔示例转账</h3><FieldList fields={[{ name: "fee", label: "手续费", value_text: "¥0.00" }, { name: "arrival", label: "预计到账", value_text: "以银行返回为准" }]} /><p>手机从下方打开，电脑从右侧展开。关闭后回到原来的位置。</p></div></DetailsDrawer>
        </section>
        <div className="ds-examples">
          <section aria-labelledby="ds-feedback-title">
            <h2 id="ds-feedback-title">每一步，都有回应</h2>
            <div className="ds-state-options" role="group" aria-label="选择状态示例">
              {([['waiting', '处理中'], ['unknown', '待核实'], ['empty', '空状态']] as const).map(([value, label]) => <Button size="sm" variant={status === value ? "default" : "outline"} aria-pressed={status === value} key={value} onClick={() => setStatus(value)}>{label}</Button>)}
            </div>
            <div className="ds-state-demo">
              {status === "waiting" && <><p className="ds-status" role="status"><Spinner />银行正在处理</p><Progress value={null} aria-label="银行办理进度" /><p>结果会显示在这里。</p></>}
              {status === "unknown" && <Notice tone="warning" title="这笔结果还在核实">请在原记录中查看最新进度。</Notice>}
              {status === "empty" && <><Users className="ds-empty-icon" aria-hidden="true" /><h3>还没有常用收款人</h3><p>首次填写后，下次办理更方便。</p></>}
            </div>
          </section>
          <section aria-labelledby="ds-loading-title"><h2 id="ds-loading-title">资料读取也有清楚的状态</h2>
            <Button variant="outline" onClick={() => setLoading(!loading)}>{loading ? "显示资料" : "查看加载状态"}</Button>
            <div className="ds-load-demo" aria-busy={loading}>{loading ? <><p role="status">正在读取您的账户…</p><Skeleton className="ds-skeleton-wide" /><Skeleton className="ds-skeleton-short" /></> : <><strong>养老金卡 · 尾号 6218</strong><p>可用余额 ¥12,680.50</p></>}</div>
          </section>
          <section className="ds-quiet-feedback"><h2>简短的提示，留在需要的地方</h2><p>点右上角“大字”试试。字号反馈轻轻出现；办理结果保留在原记录中。</p></section>
        </div>
      </div>
      <footer className="ds-footer"><span>shadcn/ui + Radix / Vaul</span><span>Lucide 图标</span><span>Sonner 轻提示</span><span>手机优先 · 键盘可用</span></footer>
    </main><Toaster />
  </div>;
}
