# 11：三条真实用户路径联调与安全复验

Ticket ID: bank-e2e-remediation/11
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 评测
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `evals/demo-remediation/`
Priority: P0/P1
Status: implemented-merged-runtime-verified
Blocked by: bank-e2e-remediation/01, bank-e2e-remediation/02, bank-e2e-remediation/03, bank-e2e-remediation/04, bank-e2e-remediation/05, bank-e2e-remediation/06, bank-e2e-remediation/07, bank-e2e-remediation/08, bank-e2e-remediation/09, bank-e2e-remediation/10
Core scenarios: S01–S08
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
复用现有诊断样例和 56 条安全数据，给目标而非固定 prompt；真实模型/HTTP/React/银行四层分别记录。

## Acceptance criteria
- [x] 三条路径有可见回执及银行计数；取消/刷新/重放/风险证据；失败样本保留；不宣称专业安全验收。
- [x] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。

2026-10-23：实现见 [PR #251](https://github.com/DrErwin/hackerthon-bank-agent/pull/251)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
