# v0.4 安全完整性（v04-security）

> Status: Confirmed — 2026-10-11 随 v0.4 正式启动建立
> 场景负责人/登记：Erwin；工作线 Owner：Ringo（PM 保留代行条款，见交付包）
> 归属目录：`backend/app/security/` 与 `evals/security/`（安全规则与安全评测归 Ringo；底座接缝归 Erwin）
> 来源：[Issue #86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[Issue #88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)（v0.3 收口遗留，[#87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87) 总索引分派）

## 1. 目的

补齐 v0.3 明示例外的安全缺口：真实风险检测器与检测层落地，安全评测达到覆盖下限，gated 轮次全部转正，使 v0.4 收口时安全证据链完整、可补验加回。

## 2. 核心验收

| 项 | 通过条件 |
|---|---|
| 真实风险检测器 + 检测层（#86） | `backend/app/security/` 交付并接入运行链路；v0.3 遗留 33 轮 gated 全部复跑转正（或如实记录余留原因与条件） |
| SEC-C-001 余 14 轮 | 依赖 #84（规划入口上下文，提供方 Erwin 底座）修复后复跑转正 |
| 覆盖下限（#88） | R06 补足差额 2 条；8 个低于 10 条的维度组补到 ≥10；SEC-E-006/v06 登记排除项修订；MAT 攻击材料改编接入 |
| 证据 | 运行报告与台账按 [evals 指南 §六](../../evals/README.md) 归档 `evals/security/`；检测器交付后 v0.3 补验加回（记录为补验，不追溯改写收口结论） |

## 3. 依赖与边界

- **依赖**：#84 规划入口上下文（Erwin 底座，v0.4 已排）——检测器实装与规格可先行，SEC-C-001 转正复跑等 #84 完成。
- **不依赖**：账单线与前端线（并行推进）。
- **边界**：安全规则、执行器与审计安全规则归 `backend/app/security/` 与安全评测目录；不动底座目录（需要接缝改动时按公共改动流程登记，由底座实施）。

## 4. 交付包

| 编号 | 交付包 | Owner | 状态 |
|---|---|---|---|
| [01](packages/01-detector-and-coverage.md) | 检测器与评测完整性（#86 + #88） | Ringo（PM 代行条款） | ready |
