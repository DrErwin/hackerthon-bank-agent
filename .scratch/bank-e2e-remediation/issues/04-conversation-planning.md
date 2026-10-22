# 04：自然语言续办与安全求助的模型入口

Ticket ID: bank-e2e-remediation/04
Package: [bank-e2e-remediation/packages/01-demo-remediation](../packages/01-demo-remediation.md)
Spec: [修复规格](../spec.md)
Type: 开发
Owner: Erwin 协调 / Codex 按用户授权代行
Directory: `backend/app/agent_platform/`
Priority: P0
Status: implemented-merged
Blocked by: 无
Core scenarios: S01 S02 S04 S05
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)

## What to build
明确输出原任务续办候选，候选绑定任务及版本，不能输出授权；对骗局求助开放语义，真实秘密仍前置拒绝；恢复前不能改任务。

## Acceptance criteria
- [x] 补充/修改/查询/取消区分；多任务歧义澄清；长诈骗输入调用失败如实保留；外来资料不得发起或续办交易。
- [x] 保留确认、专用验证、所有权和重复执行保护。

## Verification
本票通过相关目录的定向回归；真实模型/React/银行联合证据由票 11 汇总。未运行时标 NOT_RUN，不能替代专业安全审查。

## Comments
2026-10-22：用户授权范围内拆票。开发、运行验证、合入、验收分别记录。

2026-10-23： [PR #233](https://github.com/DrErwin/hackerthon-bank-agent/pull/233)，b89a2df 已完成原任务/版本/选项候选校验与秘密值拦截；定向32通过，GPT-6.1-sol 双轴代审通过。最终CI及合入待确认；真实模型联调由票11完成。

2026-10-23：实现见 [PR #233](https://github.com/DrErwin/hackerthon-bank-agent/pull/233)；用户授权 GPT-6.1-sol 双轴代审通过，非专业安全批准。相关代码测试及CI、真实路径分层见[汇总进度](../progress.md)与[票11证据](../../../evals/demo-remediation/README.md)。票10的专项UI走查仍待，不影响已记录的功能路径结论。
