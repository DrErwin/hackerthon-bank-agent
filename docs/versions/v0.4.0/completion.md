# v0.4.0 完成情况：账单、完整安全与完整前端（联动移至 v0.5）

> 状态：进行中（2026-10-11 正式启动，提前于原 10-13；**最晚 10-20 收口**〔PM 硬截止〕）。本页 2026-10-13 按实际进展重写，未验证项如实标注。

## 当前情况

- PRD 与公共契约已冻结（09-27 v1）；v0.3 于 2026-10-11 收口（含明示例外），v0.4 同日启动，范围调整为账单 + 完整安全 + 完整前端，联动移至 v0.5。
- **平台 / 底座线（Erwin，[v04-platform/01](../../../.scratch/v04-platform/packages/01-foundation-agent-mockbank.md)）**：
  - `#84` 规划入口上下文与 `#85` 确认/验证历史只读回放（后端）已收口（PR #95/#96/#104/#105 与 #109/#110/#112/#111）；`#91` 银行接缝与共用种子四票合入（PR #97/#98/#100/#102）。
  - 契约接缝两票合入（PR #113 `TaskView.module` + `BillReport`/`ExportView` 模型；PR #114 api 填 `module`）。
  - **v04-platform 四票（2026-10-13，独立子代理审查后合入）**：票01 受控报告存储 + F21（PR #115 `b8aa930`）、票02 导出链路 F22—F24（PR #119 `3955abb`，审查出 1 条阻塞当日修复）、票03 第二模块注册点与账单契约形状桩（PR #117 `f40959e`）、票04 账单任务接线 `module`/载荷/`report_ready`（PR #120 `c270abb`）；合并后主线后端全量 **431 passed**（CI 绿）。
  - **契约三处接缝提前收口（2026-10-14，[Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122)）**：按一票一目录拆 [06 契约](../../../.scratch/v04-platform/issues/06-sse-event-payload-union.md)（PR #126 `91ddc4a`）、[07 api](../../../.scratch/v04-platform/issues/07-export-task-module-and-event-payload.md)（PR #128 `77726a9`）、[08 agent_platform](../../../.scratch/v04-platform/issues/08-harness-resume-parsing.md)（PR #127 `3613ce0`），各自双轴独立子代理审查（AI 审查、非真人）后合入：`EventPayload` 收敛为通用 `TaskView`（契约 §8 轻量确认档，登记「事件载荷不做强制校验」为接受项）、导出任务 `module=bills`、harness 按模块解析第二模块载荷与跨会话恢复。合入后主线后端全量 **533 passed**、模拟银行 14 passed、各 PR CI 绿；真数据下的复验保留在票 05。前端类型重生成已发定向通知（Issue #89）。
  - **账单 L01 合并与平台侧接单（2026-10-16，[PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131) squash `85a119d`）**：三轴独立审查（规范/规格/安全，AI 审查非真人）结论**有条件可合**、无 P0，PM 决定合并；合并**行为中性**（生产装配仍挂契约形状桩，真实模块待平台接线）。审查定位三条平台级拦路＋一处平台既有缺陷，平台侧同日接单：票 05 验收口径改**分阶段**（L01 先行；L02/L03 追加；PM 接受最小切片注册＝桩整体让位），补拆 [10 规划入口支持第二业务模块](../../../.scratch/v04-platform/issues/10-planner-second-module.md)（[Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134)）、[11 拒绝路径审计 outcome 修复](../../../.scratch/v04-platform/issues/11-audit-outcome-denial.md)（[Issue #135](https://github.com/DrErwin/hackerthon-bank-agent/issues/135)）、[12 L02/L03 公共契约模型](../../../.scratch/v04-platform/issues/12-contract-l02-l03-models.md)（[Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132)）；安全侧读账口径四项开 [Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137) 转 Ringo（不代签），账单线五项返修开 [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) 转周恩宇。同日 [票 12 已合入](https://github.com/DrErwin/hackerthon-bank-agent/pull/138)（[PR #138](https://github.com/DrErwin/hackerthon-bank-agent/pull/138) squash `4ed5555`，双轴 AI 审查可合、contracts 53 passed、后端全量 596 passed、CI 绿；账单线 L02/L03 公共模型前置解除）。
  - **平台票 10/11 接力（2026-10-17）**：[票 10 规划入口支持第二业务模块](../../../.scratch/v04-platform/issues/10-planner-second-module.md) 已合入（[PR #139](https://github.com/DrErwin/hackerthon-bank-agent/pull/139) squash `15cf0ad`，双轴 AI 审查可合、`agent_platform` 125 passed、全量 601 passed、CI 绿、[Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134) 关闭）——账单任务从消息入口发起的规划侧阻塞解除，票 05 解封前置只剩安全侧读账口径（#137）。[票 11 拒绝路径审计 outcome 修复](../../../.scratch/v04-platform/issues/11-audit-outcome-denial.md) 已合入（[PR #141](https://github.com/DrErwin/hackerthon-bank-agent/pull/141) squash `294e0d4`，2026-10-18；双轴 AI 审查关键结论 + Lead 复核补全、`agent_platform` 124 passed、CI 绿、[Issue #135](https://github.com/DrErwin/hackerthon-bank-agent/issues/135) 关闭）——**平台侧补拆三票 10/11/12 全部合入**，票 05 解封前置只剩安全侧读账口径（#137）。账单线按 [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) 提交返修 [PR #140](https://github.com/DrErwin/hackerthon-bank-agent/pull/140)，三轴审查完毕（1 项 P2 文案修复合前必修，已回帖作者）。
  - 遗留已开单留档：真实账单模块接入（[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) → [v04-platform 票 05](../../../.scratch/v04-platform/issues/05-real-bills-integration.md)，`blocked`：前置=票 10 + 安全侧读账口径）、F35 管理端审计导出归属（[Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121)）；契约三处接缝（Issue #122）已于 10-14 收口（见上）。
- **账单线（周恩宇，[v04-bills/01](../../../.scratch/v04-bills/packages/01-bills-backend.md)）**：in_progress。统计内核 PR #92 已合入（10-13）；**L01 公开切片已合入 main（10-16，[PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131)，`app/modules/bills` 152 passed、CI 591 passed）**；L02/L03 开发分支已建（`feat/bills/l02-private-rules`、`feat/bills/l03-report-core`），平台 [票 12](../../../.scratch/v04-platform/issues/12-contract-l02-l03-models.md) 契约模型已于 10-16 合入、分支已 rebase，但**仍未开 PR**；五项返修已开票（[Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) → v04-ethan-bills-backend/08、/09），返修 [PR #140](https://github.com/DrErwin/hackerthon-bank-agent/pull/140) 已合入 main（10-18 squash `e7e7b8f`：三轴审查后唯一 P2 文案必修由 PM 授权代行修复并记录，后端全量 612 passed、CI 绿）；票 09 分支已备未提 PR，Issue #136 保持 OPEN；#93 评测覆盖已裁决维持不可合、转 v0.5（10-18 PM 代行记录，见 PR 评论）。评测下限实跑与前端冻结信号待完成。
- **安全线（Ringo，[v04-security/01](../../../.scratch/v04-security/packages/01-detector-and-coverage.md)）**：in_progress。2026-10-15 交付[本人规格与七张实施票](../../../.scratch/v04-ringo-security/spec.md)（代码与评测实施尚未开始）；**MAT 改编范围已由 PM 对齐为必交（2026-10-16，[Issue #133](https://github.com/DrErwin/hackerthon-bank-agent/issues/133) 结论，#88 已同步）**；读账安全口径与审计证据四项另开 [Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)，2026-10-18 已出 **v0.4 临时口径**（PM 代行、非 Ringo 本人审查，见 Issue 评论）解锁票 05，Ringo 回归后复核。
- **前端线（梁爽主责、六水协助，[frontend-complete/01](../../../.scratch/frontend-complete/packages/01-v04-complete-frontend.md)）**：in_progress。原型五类画面已走查通过（10-12）；通用底盘 PR #108 **已合入 main**（10-13）；转账真实接口与 F39 历史恢复 [PR #142](https://github.com/DrErwin/hackerthon-bank-agent/pull/142) 已开 **Draft**（18 文件 +436/−64，`npm test` 30/30、`npm run build` 通过），2026-10-18 双轴独立审查结论：**保持 Draft**——3 项必修（单条 `/records` 失败打断整页装载、重连不合并 F39 历史、adminHref 主机切换）+ 2 项硬门槛（Ringo 审查确认/验证交互、真实接口路径验收）；若抢 10-20 按「整体保留 + 3 必修 + 票面回填 + 签核或 PM 豁免」的最小切片。账单插槽（票 04）依赖账单公开能力冻结信号。
- **联合验收（[v04-bills/02](../../../.scratch/v04-bills/packages/02-v04-acceptance.md)）**：planned；已把平台线纳入参与线与 Start when（第 ④ 条含票 05），条件未齐不启动。

## 启动条件（已核验，2026-10-11）

- [x] v0.3.0 普通转账纵向链路通过联合验收（2026-10-11 收口，含明示例外）。
- [x] v0.3.0 的公共接缝和遗留问题已经记录（[Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87) 总索引）。
- [x] 负责人在正式项目跟踪表确认开始时间（PM 2026-10-11 决定启动）。

## 待完成

- 账单业务与评测：公开能力（L01—L03）、BF01—BF07 通过、评测下限与实跑证据（周恩宇）。
- 安全：真实风险检测器与评测完整性（#86/#88）——2026-10-18 PM 代行范围裁定**转 v0.5**，缺口已记录于两单评论，不代签专业结论。
- 完整前端双场景与替换（FE-01—FE-06、适老化走查，梁爽/六水）。
- 平台：真实账单模块接入与纵向联调（[票 05](../../../.scratch/v04-platform/issues/05-real-bills-integration.md)，**分阶段口径**：L01 先行、L02/L03 追加）；**前置只剩安全侧读账口径 [Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)**——票 10（规划入口）、票 11（审计 outcome）、票 12（L02/L03 契约模型）已全部合入（PR #138/#139/#141）。
- 联合验收与收口：证据汇总、`completion.md` 终稿、docs/README 与 ROADMAP 状态翻转、飞书同步与甘特图重建。
- PM 节点：10-28 答疑前确认"安全自评是否必交"、11-01 报名、11-02 提交材料（比赛材料最终制作不在本版范围）。

## 验证状态

- 平台 / 底座线已有可复核证据：各票测试、CI 与主线全量回归（合并后主线后端全量 **605 passed**），链接见各 PR 与票据 Comments；AI 审查（含独立子代理）**不代表真人专业审查**。2026-10-18 补充审查：#141 的审计 outcome 修复已合入，但**转账节点级** `task.transition` 仍把 `status=failed` 写 `succeeded`（`transfer_runtime.py:93-97`）；`unknown` 兜底使 `NEEDS_ATTENTION`/`PARTIALLY_SUCCEEDED` 由 succeeded 变 unknown（转账线可恢复的安全拒绝走的正是前者）；真实 deny-all 路径建议补 1 行 outcome 断言——待「审计 outcome 口径」小票收口。
- 账单、安全、前端三线在本版本尚无完成验证与实跑证据；代表性用例文档检查通过不替代真实运行。
- 联合验收未启动；真人专业安全审查仍待（v0.4 相关豁免记录见 [v04-platform 票 02](../../../.scratch/v04-platform/issues/02-export-chain.md) 与 PR #116/#119）。
