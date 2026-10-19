# 02：生产装配接入检测器并移除转账风险夹具依赖

Ticket ID: v04-risk-inputs/02
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: blocked（依赖 Ringo 检测器交付）
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../../v04-platform/packages/01-foundation-agent-mockbank.md)
Spec: [v04-risk-inputs 规格](../spec.md)
Core scenarios: 转账风险链路（RS01 / RS02 / RS03 生产装配侧）；对应 [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160) 第 3 项
Verification: 生产装配（`local_demo.build_runtime`）在配置检测器时只调用「可信风险输入 + 检测器」，查不到夹具；未配置检测器时 fail-closed（暂停而不是退回夹具）；固定等级夹具只在测试对照路径；真实 GLM 本地演示的转账链路回归。
Blocked by: [v04-risk-inputs/01：服务端可信风险输入读取路径与检测器接缝](01-risk-input-read-path.md)、[v04-ringo-security/02：真实风险识别与安全门组合](../../v04-ringo-security/issues/02-real-risk-detector.md)
Source issue: [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)

## 交付

1. `local_demo.build_runtime` 的风险事实回调改为：`TrustedRiskInputs.resolve(...)` → 注入的 `RiskDetector`；检测器由 `backend/app/security/` 提供（Ringo 交付后按接缝接入），装配层不写识别规则。
2. 移除真实路径对 `config.transfer_fixtures` 的信号匹配依赖；固定等级夹具只保留为流程对照（测试夹具与显式的受控演示模式，来源标记可区分），不得作为真实检测结论。
3. 未配置检测器或检测器不可用时 fail-closed：`RiskFactsUnavailable` → 安全门暂停，不静默回退预设等级。
4. 本地 `LocalDemoConfig` / 示例配置与新装配一致；README / LOCAL-DEV 说明更新。
5. 回归：本地演示装配的转账链路（含真实 GLM）与后端全量测试通过；无夹具依赖残留扫描。

## 边界

- 只改 `backend/app/agent_platform/`；检测器实现与规则归 `backend/app/security/`（Ringo）。
- 不改变高风险终止、中风险双因子、低风险基础验证的既定业务规则。

## Comments

- 2026-10-19：按 [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160) 第 3 项建立。等待 Ringo 在 security 目录交付识别入口；接缝与读取路径见 [01](01-risk-input-read-path.md)。
