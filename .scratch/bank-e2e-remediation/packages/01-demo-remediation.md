# bank-e2e-remediation/packages/01-demo-remediation：Demo 修复

Status: in_progress
Owner: Erwin（协调；AI 按票实施）
Activation: 2026-10-22 用户直接指派
Start when: 读取交接、核对最新代码与已有票
Accepted by: 用户在本聊天明确授权 Codex 承接修复；不替其他成员记录领取
Accepted at: 2026-10-22
Spec: [共享规格](../spec.md)
Work spec: [bank-e2e-remediation](../spec.md)

2026-10-23 追加授权：用户批准本聊天完整体验方案并要求开始实施，豁免每个改动单独PR，允许相关系列改动集中一个PR以减少Actions用量。按[体验规格](../experience-spec.md)及票16～21执行，保留单目录提交和分层验证。此次授权不等同专业安全验收或自动合并批准。

范围：连续办理、卡片交互、安全兜底，按单目录依次实现。依赖及验收见规格 S01～S08。验收由项目负责人决定。

2026-10-23 用户明确授权：“用6.1sol模型代审，通过后依次合并继续往后做”。本轮使用 GPT-6.1-sol 双轴代审，发现项修复并复核、相关检查通过后依次合并，再继续后续票。本记录属于用户对本轮合并审查安排的明确例外，不是 Ringo 本人批准，也不改变长期目录归属或运行时安全门。

2026-10-23：24个单目录PR #228～#251已依次合入。三条真实路径、银行计数与安全复验见[分层证据](../../../evals/demo-remediation/README.md)。实现与运行验证完成；票10专项UI检查、用户最终验收仍待。

本轮体验增量票16～21已实现、相关本地检查和真实主路径通过；[证据](../../../evals/demo-remediation/guided-experience.md)。集中PR待审，最终验收未完成。
