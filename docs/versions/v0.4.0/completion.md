# v0.4.0 完成情况：账单、完整安全与完整前端（联动移至 v0.5）

> 状态：进行中（2026-10-11 正式启动，提前于原 10-13；**最晚 10-20 收口**〔PM 硬截止〕）。本页 2026-10-13 按实际进展重写，未验证项如实标注。

## 当前情况

- PRD 与公共契约已冻结（09-27 v1）；v0.3 于 2026-10-11 收口（含明示例外），v0.4 同日启动，范围调整为账单 + 完整安全 + 完整前端，联动移至 v0.5。
- **平台 / 底座线（Erwin，[v04-platform/01](../../../.scratch/v04-platform/packages/01-foundation-agent-mockbank.md)）**：
  - `#84` 规划入口上下文与 `#85` 确认/验证历史只读回放（后端）已收口（PR #95/#96/#104/#105 与 #109/#110/#112/#111）；`#91` 银行接缝与共用种子四票合入（PR #97/#98/#100/#102）。
  - 契约接缝两票合入（PR #113 `TaskView.module` + `BillReport`/`ExportView` 模型；PR #114 api 填 `module`）。
  - **v04-platform 四票（2026-10-13，独立子代理审查后合入）**：票01 受控报告存储 + F21（PR #115 `b8aa930`）、票02 导出链路 F22—F24（PR #119 `3955abb`，审查出 1 条阻塞当日修复）、票03 第二模块注册点与账单契约形状桩（PR #117 `f40959e`）、票04 账单任务接线 `module`/载荷/`report_ready`（PR #120 `c270abb`）；合并后主线后端全量 **431 passed**（CI 绿）。
  - 遗留已开单留档：真实账单模块接入（[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) → [v04-platform 票 05](../../../.scratch/v04-platform/issues/05-real-bills-integration.md)，`blocked`）、契约三处接缝（[Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122)）、F35 管理端审计导出归属（[Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121)）。
- **账单线（周恩宇，[v04-bills/01](../../../.scratch/v04-bills/packages/01-bills-backend.md)）**：in_progress。私有统计内核与局部验证已开 PR（#92，待作者返修；#93 评测覆盖为 Draft）；真实公开能力（L01—L03）、评测下限实跑与前端冻结信号待完成。
- **安全线（Ringo 或 PM 代行，[v04-security/01](../../../.scratch/v04-security/packages/01-detector-and-coverage.md)）**：`Accepted by` 未记录，按条款 **2026-10-14 24:00 前未确认领取即由 PM 代行**；#86 检测器、#88 评测完整性未完成。
- **前端线（梁爽主责、六水协助，[frontend-complete/01](../../../.scratch/frontend-complete/packages/01-v04-complete-frontend.md)）**：in_progress。原型五类画面已走查通过（10-12）；通用底盘 PR #108 待作者返修 + PM 走查；账单插槽接入依赖账单公开能力冻结信号。
- **联合验收（[v04-bills/02](../../../.scratch/v04-bills/packages/02-v04-acceptance.md)）**：planned；已把平台线纳入参与线与 Start when（第 ④ 条含票 05），条件未齐不启动。

## 启动条件（已核验，2026-10-11）

- [x] v0.3.0 普通转账纵向链路通过联合验收（2026-10-11 收口，含明示例外）。
- [x] v0.3.0 的公共接缝和遗留问题已经记录（[Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87) 总索引）。
- [x] 负责人在正式项目跟踪表确认开始时间（PM 2026-10-11 决定启动）。

## 待完成

- 账单业务与评测：公开能力（L01—L03）、BF01—BF07 通过、评测下限与实跑证据（周恩宇）。
- 安全：真实风险检测器与评测完整性（#86/#88，Ringo 或 PM 代行）。
- 完整前端双场景与替换（FE-01—FE-06、适老化走查，梁爽/六水）。
- 平台：真实账单模块接入与纵向联调（[票 05](../../../.scratch/v04-platform/issues/05-real-bills-integration.md)，前置=账单公开能力可运行）；三处契约接缝随其收口。
- 联合验收与收口：证据汇总、`completion.md` 终稿、docs/README 与 ROADMAP 状态翻转、飞书同步与甘特图重建。
- PM 节点：10-28 答疑前确认"安全自评是否必交"、11-01 报名、11-02 提交材料（比赛材料最终制作不在本版范围）。

## 验证状态

- 平台 / 底座线已有可复核证据：各票测试、CI 与主线全量回归（合并后 431 passed），链接见各 PR 与票据 Comments；AI 审查（含独立子代理）**不代表真人专业审查**。
- 账单、安全、前端三线在本版本尚无完成验证与实跑证据；代表性用例文档检查通过不替代真实运行。
- 联合验收未启动；真人专业安全审查仍待（v0.4 相关豁免记录见 [v04-platform 票 02](../../../.scratch/v04-platform/issues/02-export-chain.md) 与 PR #116/#119）。
