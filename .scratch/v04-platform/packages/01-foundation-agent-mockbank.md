# 交付包 01：v0.4 底座、Agent 与模拟银行（API / Harness / 银行接缝）

Status: in_progress（2026-10-13 Erwin 本人接受；同日双轴审核通过并完成拆票，实施票见 [issues/01—08](../issues/)。第一块为账单线票 05 的前置，建议先做；06—08 为 Issue #122 三处接缝，2026-10-13 PM 决定提前单独收口）
Owner: **Erwin** —— 模拟银行 + API 底座 + Agent/Harness 全部归 Erwin（2026-10-13 PM 明确）
Activation: 2026-10-13 Erwin 建立，补 v0.4 缺失的底座交付包
Start when: 立即，本包不等其它线；第三块（账单模块接入平台）在账单公开能力形态未定时先用契约形状 stub
Spec: [v0.4 底座、Agent 与模拟银行场景规格](../spec.md)
Accepted by: Erwin（本人负责，不代填他人）
Accepted at: 2026-10-13
Work spec: [v0.4 底座、Agent 与模拟银行场景规格](../spec.md)；实施票 [issues/01—08](../issues/)（2026-10-13 Erwin 本人拆票 01—05；2026-10-14 按 Issue #122 补拆 06—08）

Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87)（v0.3 收尾总索引）；**报告与文件交付缺口尚无 Issue**——它是本包建立的原因，是否补一张转给 Erwin 的单子由 PM 决定（2026-10-13 发现：契约里已定义、没有任何单子覆盖）

## 业务目标

让 v0.4 的两个业务场景（转账 + 账单）在同一套平台上真正跑起来，并把「契约里已定义、还没有实现」的公共能力补齐到可用：报告与文件交付链路可用、第二个业务模块按既有注册点接入、银行接缝与共用种子支撑账单取数。

## 交付范围

1. **报告与文件交付（契约 §6.7 F21—F24）**——目录 `backend/app/api/`（必要时 `backend/app/contracts/` 补字段）：
   受控报告存储与读取（F21）、卡片导出（F22，普通操作）、明细导出（F22 details，敏感，**必须再次完成本次所需验证**）、导出状态查询（F23）、受控下载（F24）。契约模型 `BillReport` / `ExportView` 已于 2026-10-12 合入（PR #113）。
   依赖：明细导出的「再次验证」复用 `backend/app/security/` 既有验证机制与 F16—F20 口径（Ringo 目录不改；PR 开出后请 Ringo 审查，如需新规则由安全线在 v04-security 登记）；金额与分类事实来自账单模块的受控报告（周恩宇）。
2. **第二个业务模块（账单）接入平台**——目录 `backend/app/api/`、`backend/app/agent_platform/`：
   能力注册与意图路由、任务视图（`module=bills` + 账单载荷）、事件与恢复口径；不复制转账运行体系，不新建第二套底座。
   依赖：账单公开能力（`bills.summarize` / `detect_anomalies` / `generate_report`）形态确定；未就绪时用契约形状 stub 先行。
3. **模拟银行与接缝维护**——目录 `backend/app/services/`、`backend/app/storage/`、`evals/mockbank/`：
   已交付并记录：#91（B08 取数、账本事实列、共用种子、本机演示启用，PR #97/#98/#100/#102）。本包负责按账单 / 前端联调反馈继续扩接缝，无新需求时不开票。
4. **契约受理与联调**——受理各线契约缺口（公共改动流程登记 → 底座实现或明确拒绝）、处理转账 / 账单 / 前端联调中的接口问题（[会议纪要](../../../docs/meetings/2026-10-12_v0.4阶段同步会-会议纪要.md)：底座负责契约审查与联调）。

## 向其它工作线提供什么

- **给账单线**：F21—F24 报告与文件交付接口 → [v04-ethan-bills-backend/05：L03受控报告与导出接线](../../v04-ethan-bills-backend/issues/05-report-export.md) 的解除条件；银行接缝与共用种子。
- **给前端线**：账单任务在平台可用（`module=bills` + 载荷）与报告 / 导出视图的真实数据来源；账单插槽的接入条件与冻结信号仍以 [v04-bills/01](../../v04-bills/packages/01-bills-backend.md) / [frontend-complete/01](../../frontend-complete/packages/01-v04-complete-frontend.md) 口径为准。
- **给安全线**：明细导出再验证的接口位置与调用口径（`security/` 侧规则由 Ringo 定）。
- **给联合验收**：本包证据并入 [v04-bills/02](../../v04-bills/packages/02-v04-acceptance.md)。

## 验收标准

1. 规格 P01—P06 逐条有可复核证据；E2E 优先（真实运行时 + 模拟银行 + 安全门既有路径）。
2. 报告与导出：本人范围校验、明细导出未过验证不给内容、下载路径受控、无验证码或秘密泄漏。
3. 一票一目录一分支一 PR；不跨目录改业务模块与 `backend/app/security/`。
4. 契约变更按第 8 章登记（轻量 / 协同），旧调用不被破坏或有明确切换窗口。
5. 账单线票 05 与前端账单插槽能用本包接口真实联调，联调证据进联合验收。

## 实施票（2026-10-13 双轴审核通过后建立，一票一目录一分支一 PR）

| 票 | 目录 | 交付 | 前置 |
|---|---|---|---|
| [01](../issues/01-report-storage-read.md) | `backend/app/api/` | 受控报告存储（`BillReport` 落库写路径）+ F21 读取 | 无（契约模型已合 PR #113） |
| [02](../issues/02-export-chain.md) | `backend/app/api/` | F22 卡片/明细导出（明细再验证）+ F23 状态 + F24 受控下载（card/details 分支） | 01；跨线依赖安全侧口径（Ringo，PR 请其审查） |
| [03](../issues/03-bills-registration.md) | `backend/app/agent_platform/` | 账单能力注册（L01—L03 manifest）+ 意图路由 + 模块应用工厂 | 跨线等 v04-bills/01 冻结信号（未定用契约形状 stub 先行，不构成实施前置） |
| [04](../issues/04-bills-task-wiring.md) | `backend/app/api/` | 账单任务接线：任务视图 `module=bills` + 载荷 + `task_updated` / `report_ready` 事件 + 恢复口径 | 03；01（`report_ready` 引用已落库报告） |
| [05](../issues/05-real-bills-integration.md) | `backend/app/api/` | 真实账单模块接入（替换契约形状桩）+ 账单纵向端到端联调；同窗口复验 Issue #122 三处接缝在真数据下的表现 | `blocked`：账单公开能力可运行（周恩宇 v04-bills/01，跨线）；Issue [#123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) |
| [06](../issues/06-sse-event-payload-union.md) | `backend/app/contracts/` | Issue #122 第 1 项（契约侧）：`EventPayload` 收敛为通用 `TaskView` + §8 登记 | 无（2026-10-13 PM 决定提前单独收口） |
| [07](../issues/07-export-task-module-and-event-payload.md) | `backend/app/api/` | Issue #122 第 3 项 + 第 1 项 API 侧：导出任务 `module=bills`、去掉事件去载荷兜底 | `blocked`：06 合入 |
| [08](../issues/08-harness-resume-parsing.md) | `backend/app/agent_platform/` | Issue #122 第 2 项：harness 恢复解析去转账定型 | 无 |

原建议「账单模块接入平台」跨 `api/ + agent_platform/` 两目录，按一票一目录拆为 03 + 04（2026-10-13 审核意见）；银行接缝 / 种子扩展按联调反馈触发，触发时按一票一目录另开票（06 起），无需求不开票。**票 05** 由 2026-10-13 盘点补齐：03/04 只交付注册点与契约形状桩，真实账单链路需要接入票（Issue #123）。

票由 Owner 本人建立（2026-10-13），本包不代拆、不代填他人接受。

## 不在本包范围

- 账单模块业务实现与评测（周恩宇，[v04-bills/01](../../v04-bills/packages/01-bills-backend.md)）。
- 安全策略、执行器、验证与安全评测（Ringo，[v04-security/01](../../v04-security/packages/01-detector-and-coverage.md)）。
- 完整前端与适老化（梁爽、六水，[frontend-complete/01](../../frontend-complete/packages/01-v04-complete-frontend.md)）。
- 联动（v0.5）、版本收口与比赛材料（[v04-bills/02](../../v04-bills/packages/02-v04-acceptance.md)、PM）。
- 管理端审计导出 F35 与 F24 的 audit 分支（契约 §6.8 已定义、未实现，F33/F34 已在 main 只差导出端点）——不随本包票交付，归属由 PM 决定（2026-10-13 审核发现，已开 [Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121) 留档）。
- 契约层三处接缝（SSE 事件载荷联合类型仍按转账定型、harness 恢复解析同因、导出任务 `module` 显示 transfer）——已开 [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 留档。2026-10-13 PM 决定提前单独收口，按一票一目录拆为 [06](../issues/06-sse-event-payload-union.md)（contracts）/ [07](../issues/07-export-task-module-and-event-payload.md)（api）/ [08](../issues/08-harness-resume-parsing.md)（agent_platform）；票 05 保留真数据下的复验。

## Comments

- 2026-10-13 Erwin：v0.4 缺底座交付包，导致「契约已定义但未实现」的报告导出接口没有归属 → 建本包，明确模拟银行、API 底座、Agent/Harness 归 Erwin。
- 2026-10-13 双轴审核（Standards / Spec 子代理 + PM 会话独立核对；AI 审查、非真人）：**无阻塞项、可拆票**，意见当日处置——拆票表按一票一目录重排（原建议 03 拆 03+04）、spec 补测试覆盖框架并限定 P05 判词为接缝三态、`report_ready` 事件归票 04、给前端线措辞对齐 frontend-complete/01、票 05 引用改完整票号、Status 转 in_progress、Work spec 回填；F35 归属与 Ringo 依赖通知待 PM 决定。实施票 issues/01—04 同日建立。
- 2026-10-13 四票经独立子代理审查后全部合入 main（01 `b8aa930` / 02 `3955abb` / 03 `f40959e` / 04 `c270abb`，审查处置见各 PR；合并后主线后端全量 431 passed）。
- 2026-10-13 PM 盘点补齐归属：[票 05 真实账单模块接入与纵向联调](../issues/05-real-bills-integration.md) 建立（`blocked`，前置=账单公开能力可运行）；F35 归属开 [Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121)、接缝留档开 [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122)、接入缺口开 [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)。
- 2026-10-14 Erwin（AI 代填，PM 决定）：Issue #122 三处接缝提前单独收口，按一票一目录补拆 [06](../issues/06-sse-event-payload-union.md)（contracts）/ [07](../issues/07-export-task-module-and-event-payload.md)（api，`blocked` 于 06）/ [08](../issues/08-harness-resume-parsing.md)（agent_platform）；票 05 的主体仍 `blocked` 于账单公开能力，保留真数据下的复验。
