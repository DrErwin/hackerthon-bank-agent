# 02：联合执行与证据共用

Ticket ID: v03-security-eval-integration/02
Package: [交付包03](../../transfer-agent-framework/packages/03-v03-evaluation.md)
Spec: [安全评测接入规格](../spec.md)
Type: 开发
Owner: 用户授权AI接入；Ringo专业审查待记录
Directory: evals/security/
Status: ready-for-agent
Blocked by: [v03-security-eval-integration/01：程序安全评测](./01-program.md) 的代码交付
Core scenarios: SI06
Verification: 本票自动断言、故障及缺口反例、相关离线流程；联合验收仍归原票12。
Accepted by: 用户授权AI
Accepted at: 2026-10-07

## What to build

同次运行关联功能与安全编号，先核对兼容条件，再用独立安全断言判定；缺证据Blocked，突变反例不能Passed。

## Acceptance criteria

- [ ] 同次运行关联功能与安全编号，先核对兼容条件，再用独立安全断言判定；缺证据Blocked，突变反例不能Passed。
- [ ] 不修改原JSONL、历史模板或后端业务规则；本票代码只落evals/security/。
- [ ] 保存真实执行与离线替代边界；未调用付费真实模型，Ringo审查单列。
- [ ] 本票专项及受影响核心路径验证、有独立分支/PR和双轴AI审查证据。

## Comments

2026-10-07本轮只交付规格与票据。用户明确要求“只执行到拆票，实施先不做”；本票未领取实施，未写代码、未运行评测。实施须等待用户后续明确启动及前置票交付。
