# v0.5.0 完成情况：系统验收与体验打磨

> 状态：**进行中**（2026-10-21 起，目标 10-30）。
> 口径：按实际交付与证据记录；AI 代行实施与审查不等于真人审查，也不等于 Ringo 安全签核。当前任务与开放问题见[项目跟踪](../../01-项目跟踪.md)。

## 一、已交付

| 日期 | 交付 | 提交 / 证据 | 边界与未做 |
|---|---|---|---|
| 10-24 | **联动 G1 闭合与包 03 业务两票实施**：平台输入核对 PR [#264](https://github.com/DrErwin/hackerthon-bank-agent/pull/264)、订阅类型化入口 PR [#266](https://github.com/DrErwin/hackerthon-bank-agent/pull/266)（均 CI 绿、子代理审查通过后合入）；票 01 减支编排+共用计划骨架 PR [#269](https://github.com/DrErwin/hackerthon-bank-agent/pull/269)、票 02 养老金安排与留存核算 PR [#268](https://github.com/DrErwin/hackerthon-bank-agent/pull/268) 已实现，cross 目录测试 21 项全绿，审查进行中 | 账单入口类型化输入缺口交账单负责人；票 03 生日阻塞于 Ringo 安全 01（planned）；平台 05/09 装配、前端、包 05 E2E 与真人签核未做 |
| 10-24 | 联动包 03/05 阶段转派、03 接包与三票细化 | Erwin 本人确认；[包 03 规格](../../../.scratch/v05-cross-business/spec.md)及[交接](../../../.scratch/v05-cross-business/handoff.md) | 05 尚未领取；G1 输入支持及安全/票面前置未闭合；未写业务代码或运行 E2E |
| 10-24 | **联动平台底座七票实施**（v05-cross-platform 01/02/03/04/06/07/08） | PR [#256](https://github.com/DrErwin/hackerthon-bank-agent/pull/256)/[#257](https://github.com/DrErwin/hackerthon-bank-agent/pull/257)/[#258](https://github.com/DrErwin/hackerthon-bank-agent/pull/258)/[#259](https://github.com/DrErwin/hackerthon-bank-agent/pull/259)/[#260](https://github.com/DrErwin/hackerthon-bank-agent/pull/260)+[#261](https://github.com/DrErwin/hackerthon-bank-agent/pull/261)/[#262](https://github.com/DrErwin/hackerthon-bank-agent/pull/262)/[#263](https://github.com/DrErwin/hackerthon-bank-agent/pull/263)（均 CI 绿）。公共模型+契约 §5.4 修订；应用库 v5（父子关系/D1 资金安排原子接缝/预算占用串行/受控资料）；受控子任务派发与恢复+D1 普通转账提交前暂停（银行零写入）；通用 children 端点；银行库 v4 原子对象+核销流水对手方回填；B10—B13/B20—B22 服务与网关默认拒绝写入+响应丢失故障；F36 配送受控录入。每票子代理审查（发现的 2 个必须项均已修复复测）+票面回交 | 票 05/09 阻塞于 v05-cross-business（未代写）；D1 错误呈现 source/field 偏差待转账负责人适配；Ringo 安全审查、前端接入、E2E、真人签核未做；合入前后端全量 1469 passed |
| 10-24 | 联动后续工作交接 | [执行交接](../../../.scratch/v05-cross-platform/handoff.md)：补齐票一收口步骤、九票顺序、跨包开始条件、决策分工及可转交指令 | 交接文档已准备；未代执行者接票，未实施代码或运行 E2E |
| 10-24 | 联动票 01 约定裁定材料 | [裁定稿](../../../.scratch/v05-cross-platform/01-decision.md)、[字段与样例](../../../.scratch/v05-cross-platform/01-contract-detail.md)；源码核对确认复用部分完成状态及配送 F36 | Erwin 已确认 D1/D2 业务规则，具体契约及必要安全确认仍待完成；未实现公共模型、未运行模型测试/E2E，不代表开发票完成 |
| 10-24 | 第一个联动包接包与九票细化 | Erwin 本人明确接受；[执行交接](../../../.scratch/v05-cross-platform/handoff.md)与九票增加输入输出、边界及验证步骤 | 公共约定/安全审阅待确认；具体执行者由 Erwin 指派；代码和 E2E 未启动 |
| 10-24 | 联动共享规格、六包及 21 张规划票 | [规格](../../../.scratch/v05-cross-linkage/spec.md)、[公共约定方案](../../../.scratch/v05-cross-linkage/contract-proposal.md)、[正式票索引](../../../.scratch/v05-cross-linkage/ticket-proposal.md)；PM 已批准顺序和拆分 | 公共约定细节/安全审阅仍待完成；各负责人未代领，代码与 E2E 未开始 |
| 10-24 | 跨场景联动 PRD 重写（需求文档） | [PRD](../../prd/06-跨场景联动-PRD-2026-09-23.md)、[E2E 用例设计](../../../evals/cross/representative-cases.md)；PM 已确认三个生活场景，补齐 AI / Harness / 确定性业务边界 | 新增公共约定待收口；实施未开工、未拆票、未运行联动 E2E，不代表功能交付或安全签核 |
| 10-21 | 管理端审计导出 F35 / F24 audit 分支（[#214](https://github.com/DrErwin/hackerthon-bank-agent/pull/214)） | `b01ceb9`；E2E 117 passed、后端全量 1191 passed、真实演示库 3636 事件证据包 | 管理前端入口按 PM 决定未做（已知限制） |
| 10-22 | 可信观察接缝与四项体验能力（[#216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)，[交付记录](../../../evals/security/observers-2026-10-22.md)） | 九票合入；离线 E2E 26 checked / 0 failed、真实模型 GLM Coding Plan 6 次调用全 Passed | 前端粘贴框与记忆管理页未做（须 PM 同意另开前端票）、生产检测器 #160 未做、真实页面粘贴走查与批次 B/C 全量未做 |
| 10-22 | 演示 E2E 修复与卡片版式（#228–#252，[逐票进度](../../../.scratch/bank-e2e-remediation/progress.md)） | 真实三条演示路径、银行计数、56 条独立分类探针；前端 59 项测试、build、CI 与 AI 双轴代审通过 | 真实 200% 缩放、用户最终体验验收未做；Issue #227 保持开放 |
| 10-23 | 连续办理体验（[#253](https://github.com/DrErwin/hackerthon-bank-agent/pull/253)） | `b7fdd91`；可选资料、中途查询、明确反馈、结果刷新；真实模型 + HTTP + 隔离模拟银行走通转账全链路 | 200%/读屏未重跑；AI 双轴代审，非真人、非 Ringo 签核 |
| 10-23 | 连续退订与业务 E2E 修复（[#254](https://github.com/DrErwin/hackerthon-bank-agent/pull/254)） | `0e34351`；验证复用、断线补读、账单刷新保留范围、可读失败原因；后端 1431 passed、前端 70 passed | 同上 |
| 10-22～10-23 | **订阅场景前端插槽**（清单/退订/回执/刷新） | #230–#232、#247、#253/#254；真实页面取消优酷（专用验证 + 银行成功）、连续退订优酷→网盘、清单自动刷新至 0 项 0 元 | 卡片未单独标「7 天内会扣款」角标（回复文案已含）；200%/读屏属全局缺口 |

本阶段分工：2026-10-24 起，包 03/05 执行负责人为 Erwin，期限至 v0.5 本包收口；由 Erwin 组织审查并记录实际人选，安全仍由 Ringo 审查。收口交接接口、证据及遗留，后续阶段重新分派，不自动改变长期目录归属。

## 二、未完成（v0.5 剩余）

| 事项 | 负责人 | 状态 |
|---|---|---|
| 跨场景联动：业务能力、评测与前端接入 | Erwin（v0.5 业务及 E2E）、梁爽/六水（前端）；公共及模拟银行依赖 Erwin，安全 Ringo | **平台底座包 9 票中 7 票已合入**（公共模型/存储/派发/API/银行/配送，见上表）；票 05/09 与真实联动装配阻塞于 v05-cross-business 包（Erwin 已接包并细化三票，未实施）；新增 G1 平台子调用账单/订阅输入支持缺口。E2E 包转给 Erwin 未领取；安全/前端/银行专项仍未接。三个场景 E2E 均缺实现，生日另缺业务编排接入（银行能力已具备） |
| 生产检测器装配（[#160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)） | Ringo / 平台 | v0.4 起 deferred，未做 |
| 安全样例扩充（[#215](https://github.com/DrErwin/hackerthon-bank-agent/issues/215)） | Ringo | 首批 56 条已提交；**PM 2026-10-24 决定只扩充样例、不再做候选模型比较** |
| 200% 缩放、完整读屏、真机软键盘 | 前端 | 未做 |
| Ringo 真人安全签核 | Ringo | 缺；v0.4 已按 PM 豁免如实留痕 |
| 用户最终体验验收（#227） | PM | 待做 |

## 三、验收标准进度

1. **既有业务与三个联动目标的正常及关键异常 E2E**：转账、账单、订阅已在 v0.4 验证（含例外）；联动平台底座（公共模型/存储/派发/API/银行/配送）已合入但业务编排与页面未接，三主线 E2E 未开始，**本条未达成**。
2. **安全评测证明确认、权限、注入防御和隐私边界**：离线全量 20 Passed / 0 Failed / 337 Blocked、真实模型批次 A 24 轮、页面回归 24/24 已有证据；批次 B/C 解门验证与安全侧真人复核仍缺，**部分达成**。
3. **演示环境可重置、结果可重复**：本机演示库可重置，证据按票归档；尚未形成独立的"可重置 + 可重复"验收记录，**部分达成**。
4. **已知限制和遗留问题有明确记录**：v0.4 例外 E1—E10 与本页剩余项均已登记，**达成**。

## 四、启动条件

- [x] v0.4 三场景与完整安全能力完成（2026-10-22 联合验收，含例外）。
- [x] 各负责人提交可重复运行的评测与已知问题（转账/账单/订阅/安全均有评测与证据；联动尚未开始）。

## 五、验证状态

- 2026-10-24（联动平台底座七票）：分票验证——contracts 81、storage 38（应用库 31+银行库 38 分列计 37+新增）、agent_platform 238、api 175、services 59 passed；#258 合入前后端全量 `1460 passed`、#260/#262 期间全量 `1469 passed`；PR #256—#263 CI 全绿。
- 2026-10-23（#254 rebase 后、推送前）：后端 `1431 passed / 0 failed`、mockbank `14 passed`、前端 `70 passed`、`npm run build` 通过、链接与空白检查通过；#253/#254 的 PR CI 与 main 推送 CI 均绿。
- 本轮验证为 AI 代行执行与整理，**不是真人审查、不是 Ringo 专业安全签核**；用户最终体验验收与 200% 缩放/读屏未做。
