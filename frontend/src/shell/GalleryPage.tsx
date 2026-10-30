// Static walk-through of every shell card state, for design review and accessibility checks.
// All values are fixtures; nothing here talks to a data source.
import type { ReactNode } from "react";
import type { ConfirmationView, VerificationView } from "../contracts";
import { ExpiredBanner, MessageBubble, TopBar, TypingBubble } from "./components/Chrome";
import { ConfirmationCard } from "./components/ConfirmationCard";
import { Notice } from "./components/Primitives";
import { InputCard, NeedsAttentionCard, RecoveryCard, ReportCard, ResultCard, WaitingCard } from "./components/StatusCards";
import { VerificationCard } from "./components/VerificationCard";
import type { DisplayField } from "./types";

const at = "2026-10-12T10:00:00.000Z";
const later = "2026-10-12T10:05:00.000Z";
const noop = () => undefined;
const facts: DisplayField[] = [
  { name: "payee", label: "收款人", value_text: "妈妈（尾号 6688）" },
  { name: "amount", label: "金额", value_text: "¥500.00" },
];
const confirmationFields: DisplayField[] = [
  ...facts,
  { name: "payer", label: "转出账户", value_text: "主账户（尾号 1234）" },
  { name: "fee", label: "手续费", value_text: "¥0.00" },
];
const confirmation: ConfirmationView = {
  confirmation_id: "g-confirmation", task_id: "g-task", confirmation_version: 1,
  display_fields: [confirmationFields[0], ...confirmationFields.slice(1)], created_at: at, expires_at: later, decision: "pending",
};
const verification: VerificationView = {
  challenge_id: "g-challenge", task_id: "g-task", created_at: at, summary: null, required_methods: ["code", "mock_face"],
  code_expires_at: later, face_started_at: null, face_expires_at: null, code_result: "pending", face_result: "pending",
  challenge_status: "pending", consecutive_code_failures: 0,
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="sh-gallery-section">
      <h2>{title}</h2>
      <div className="sh-gallery-stack">{children}</div>
    </section>
  );
}

export function GalleryPage() {
  return (
    <div className="sh-root sh-gallery">
      <TopBar title="底盘组件状态目录" connected expired={false} origin="stub" userDisplay="全部为演示数据" />
      <main className="sh-gallery-main">
        <Section title="消息与等待">
          <MessageBubble message={{ message_id: "g1", thread_id: "g", role: "user", text: "转给妈妈500块", created_at: at, task_ids: [], report_ids: [] }} />
          <MessageBubble message={{ message_id: "g2", thread_id: "g", role: "assistant", text: "好的，我帮您办一笔转账。", created_at: at, task_ids: [], report_ids: [] }} />
          <TypingBubble />
          <WaitingCard id="g-wait" message="银行正在处理，请稍等，完成后会显示结果。" facts={facts} />
        </Section>
        <Section title="补充信息（候选）">
          <InputCard id="g-in1" active busy={false} selectedLabel={null} onSelect={noop}
            interaction={{ interaction_id: "i", kind: "input", prompt: "请选择收款人：", required_fields: [], record_ref: null, options: [{ id: "a", label: "妈妈 · 尾号 6688（常用收款人）" }, { id: "b", label: "张阿姨 · 尾号 3166（最近转过）" }] }} />
          <InputCard id="g-in2" active={false} busy={false} selectedLabel="妈妈 · 尾号 6688（常用收款人）" onSelect={noop}
            interaction={{ interaction_id: "i2", kind: "input", prompt: "请选择收款人：", required_fields: [], record_ref: null, options: [] }} />
        </Section>
        <Section title="确认单">
          <ConfirmationCard id="g-c1" view={confirmation} title="请确认这笔转账" emphasize="amount" active canConfirm canCancel busy={false} extraActions={[{ label: "返回修改（业务插槽提供）", onClick: noop }]} onAnswer={noop} />
          <ConfirmationCard id="g-c2" view={{ ...confirmation, decision: "approved" }} title="" emphasize="amount" active={false} canConfirm={false} canCancel={false} busy={false} extraActions={[]} onAnswer={noop} />
          <ConfirmationCard id="g-c3" view={{ ...confirmation, decision: "superseded" }} title="" active={false} canConfirm={false} canCancel={false} busy={false} extraActions={[]} onAnswer={noop} />
        </Section>
        <Section title="验证码 + 模拟人脸（两项都要通过）">
          <VerificationCard id="g-v1" view={verification} active canVerify busy={false} adminHref={null} onSubmitCode={async () => null} onResend={noop} onStartFace={noop} onShowDemoCode={async () => ({ challenge_id: "g-challenge", code: "123456", expires_at: later })} />
          <VerificationCard id="g-v2" view={{ ...verification, code_result: "passed" }} active canVerify busy={false} adminHref={null} onSubmitCode={async () => null} onResend={noop} onStartFace={noop} onShowDemoCode={async () => null} />
          <VerificationCard id="g-v3" view={{ ...verification, code_result: "passed", face_started_at: at, face_expires_at: later }} active canVerify busy={false} adminHref="/v04/admin" onSubmitCode={async () => null} onResend={noop} onStartFace={noop} onShowDemoCode={async () => null} />
          <VerificationCard id="g-v4" view={{ ...verification, code_result: "passed", face_started_at: at, face_result: "passed", challenge_status: "passed" }} active={false} canVerify={false} busy={false} adminHref={null} onSubmitCode={async () => null} onResend={noop} onStartFace={noop} onShowDemoCode={async () => null} />
          <VerificationCard id="g-v5" view={{ ...verification, code_result: "passed", face_started_at: at, face_result: "failed", challenge_status: "failed" }} active={false} canVerify={false} busy={false} adminHref={null} onSubmitCode={async () => null} onResend={noop} onStartFace={noop} onShowDemoCode={async () => null} />
        </Section>
        <Section title="结果与报告">
          <ResultCard id="g-r1" origin="stub" view={{ tone: "success", title: "转账成功", headline: "¥500.00", fields: [facts[0], { name: "transaction", label: "交易号", value_text: "DEMO-20261012-1" }] }} />
          <ResultCard id="g-r2" origin="stub" view={{ tone: "danger", title: "这笔钱没有转出去", fields: facts }} />
          <ResultCard id="g-r3" origin="stub" view={{ tone: "neutral", title: "已取消，没有转出", fields: facts }} />
          <ReportCard id="g-rep" origin="stub" view={{
            title: "报告卡示例", periodLabel: "演示区间（示例）", headline: { label: "合计（示例）", value: "¥0.00" },
            fields: [{ name: "a", label: "示例项一", value_text: "示例值" }, { name: "b", label: "示例项二", value_text: "示例值" }],
            note: "报告卡只演示版式；账单数字将由账单插槽按接口返回填入。",
          }} />
        </Section>
        <Section title="结果待核实与刷新恢复">
          <NeedsAttentionCard id="g-na" facts={facts} message="银行的结果暂时没有返回。" canQuery busy={false} onQuery={noop} />
          <RecoveryCard id="g-rc1" facts={facts} reason={null} canDiscard busy={false} onResume={noop} onDiscard={noop} />
        </Section>
        <Section title="错误与异常">
          <Notice tone="danger" title="原因说明"><p>验证码不正确。按安全规则本次办理已终止，没有提交给银行。</p></Notice>
          <Notice tone="warning" title="刚才的操作没有完成" action={<button type="button" className="sh-btn sh-btn-secondary">刷新</button>}>这张确认单已经失效，请以最新的确认单为准。</Notice>
          <Notice tone="info" title="提示">连接有点不稳定，页面会自动补齐最新状态。</Notice>
          <ExpiredBanner onReenter={noop} />
        </Section>
      </main>
    </div>
  );
}
