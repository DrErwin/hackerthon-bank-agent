# 01：当前96条固定模型独立安全判断

Ticket ID: v05-security-acceptance/01
Package: [v04-security/packages/01-detector-and-coverage：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [安全分层验收](../spec.md)
Type: 评测（含运行器开发）
Owner: Erwin；Codex 按本轮授权实施
Directory: `evals/security/`
Status: in_progress — 2026-10-27 中控正式恢复执行
Blocked by: None（B26与生日安全提供前置已交付，96真实批获准）
Core scenarios: [SA01](../spec.md#solution--core-scenarios)

## What to build

对原样保留的当前96条判断集，用现有glm-5.3 Coding Plan、固定prompt/随机种子执行一轮独立观测；输出完整分母、错误、脱敏原始证据、实际调用/模型/hash/费用可得值。该结果不是运行时资金安全门通过。

## Acceptance criteria

- [ ] 离线验证：完整input与来源边界入提示，答案/id/split等元数据不入提示。
- [ ] 无重试/调参；格式错误、超时、服务失败为ERROR，保留分母和安全错误类型；原始回复先脱敏再落盘。
- [ ] 当前96条一次实际运行，逐条结果和分维度/分组指标可重算；旧样例、旧56脚本和历史分母不变。
- [ ] 实际配置只读使用，密钥不打印/复制，模型/端点固定；报告明确真实调用数、usage、费用不可得项。
- [ ] 独立PR交中控两轴审查，不自行合入或代签接受。

Verification: 先运行器局部离线行为测试，再现有模型实际批次；结果先仓库外新路径，归档原始脱敏证据与双SHA256。

## Comments

2026-10-27：已建独立worktree/分支。只读核对完成，尚未编写运行器、未发起真实调用。按中控新优先级保存干净规划检查点后转services必要前置。
