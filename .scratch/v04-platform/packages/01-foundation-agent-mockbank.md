# 交付包 01：v0.4 底座、Agent 与模拟银行（API / Harness / 银行接缝）

Status: ready（包建立即可开工；第一块为账单线票 05 的前置，建议先做）
Owner: **Erwin** —— 模拟银行 + API 底座 + Agent/Harness 全部归 Erwin（2026-10-13 PM 明确）
Activation: 2026-10-13 Erwin 建立，补 v0.4 缺失的底座交付包
Start when: 立即，本包不等其它线；第三块（账单模块接入平台）在账单公开能力形态未定时先用契约形状 stub
Spec: [v0.4 底座、Agent 与模拟银行场景规格](../spec.md)
Accepted by: Erwin（本人负责，不代填他人）
Accepted at: 2026-10-13
Work spec: 接包后在本目录 `issues/` 建立（Erwin 自拆）

Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87)（v0.3 收尾总索引）；**报告与文件交付缺口尚无 Issue**——它是本包建立的原因，是否补一张转给 Erwin 的单子由 PM 决定（2026-10-13 发现：契约里已定义、没有任何单子覆盖）

## 业务目标

让 v0.4 的两个业务场景（转账 + 账单）在同一套平台上真正跑起来，并把「契约里已定义、还没有实现」的公共能力补齐到可用：报告与文件交付链路可用、第二个业务模块按既有注册点接入、银行接缝与共用种子支撑账单取数。

## 交付范围

1. **报告与文件交付（契约 §6.7 F21—F24）**——目录 `backend/app/api/`（必要时 `backend/app/contracts/` 补字段）：
   受控报告存储与读取（F21）、卡片导出（F22，普通操作）、明细导出（F22 details，敏感，**必须再次完成本次所需验证**）、导出状态查询（F23）、受控下载（F24）。契约模型 `BillReport` / `ExportView` 已于 2026-10-12 合入（PR #113）。
   依赖：明细导出的「再次验证」需要安全侧口径（Ringo）；金额与分类事实来自账单模块的受控报告（周恩宇）。
2. **第二个业务模块（账单）接入平台**——目录 `backend/app/api/`、`backend/app/agent_platform/`：
   能力注册与意图路由、任务视图（`module=bills` + 账单载荷）、事件与恢复口径；不复制转账运行体系，不新建第二套底座。
   依赖：账单公开能力（`bills.summarize` / `detect_anomalies` / `generate_report`）形态确定；未就绪时用契约形状 stub 先行。
3. **模拟银行与接缝维护**——目录 `backend/app/services/`、`backend/app/storage/`、`evals/mockbank/`：
   已交付并记录：#91（B08 取数、账本事实列、共用种子、本机演示启用，PR #97/#98/#100/#102）。本包负责按账单 / 前端联调反馈继续扩接缝，无新需求时不开票。
4. **契约受理与联调**——受理各线契约缺口（公共改动流程登记 → 底座实现或明确拒绝）、处理转账 / 账单 / 前端联调中的接口问题（[会议纪要](../../../docs/meetings/2026-10-12_v0.4阶段同步会-会议纪要.md)：底座负责契约审查与联调）。

## 向其它工作线提供什么

- **给账单线**：F21—F24 报告与文件交付接口 → [票 05 报告导出](../../v04-ethan-bills-backend/issues/05-report-export.md) 的解除条件；银行接缝与共用种子。
- **给前端线**：账单任务在平台可用（`module=bills` + 载荷）→ 账单插槽真实接入；报告 / 导出视图的真实数据来源。
- **给安全线**：明细导出再验证的接口位置与调用口径（`security/` 侧规则由 Ringo 定）。
- **给联合验收**：本包证据并入 [v04-bills/02](../../v04-bills/packages/02-v04-acceptance.md)。

## 验收标准

1. 规格 P01—P06 逐条有可复核证据；E2E 优先（真实运行时 + 模拟银行 + 安全门既有路径）。
2. 报告与导出：本人范围校验、明细导出未过验证不给内容、下载路径受控、无验证码或秘密泄漏。
3. 一票一目录一分支一 PR；不跨目录改业务模块与 `backend/app/security/`。
4. 契约变更按第 8 章登记（轻量 / 协同），旧调用不被破坏或有明确切换窗口。
5. 账单线票 05 与前端账单插槽能用本包接口真实联调，联调证据进联合验收。

## 建议拆票（接包后 to-tickets，编号以本目录为准）

| 建议票 | 目录 | 交付 | 前置 |
|---|---|---|---|
| 01 | `backend/app/api/` | 受控报告存储 + F21 读取 | 无（契约模型已合 PR #113） |
| 02 | `backend/app/api/` | 卡片导出 + 明细导出（再验证）+ F23 状态 + F24 受控下载 | 01；明细再验证需安全侧口径 |
| 03 | `backend/app/api/` + `backend/app/agent_platform/` | 账单模块接入平台（注册 / 路由 / 任务视图 / 事件） | 账单公开能力形态；未定用 stub |
| 04 | `backend/app/services/`、`storage/` | 按联调反馈扩银行接缝 / 种子（按需，无需求不开票） | 联调发现 |

票在接包后建立，本包不代拆、不代填他人接受。

## 不在本包范围

- 账单模块业务实现与评测（周恩宇，[v04-bills/01](../../v04-bills/packages/01-bills-backend.md)）。
- 安全策略、执行器、验证与安全评测（Ringo，[v04-security/01](../../v04-security/packages/01-detector-and-coverage.md)）。
- 完整前端与适老化（梁爽、六水，[frontend-complete/01](../../frontend-complete/packages/01-v04-complete-frontend.md)）。
- 联动（v0.5）、版本收口与比赛材料（[v04-bills/02](../../v04-bills/packages/02-v04-acceptance.md)、PM）。

## Comments

- 2026-10-13 Erwin：v0.4 缺底座交付包，导致「契约已定义但未实现」的报告导出接口没有归属 → 建本包，明确模拟银行、API 底座、Agent/Harness 归 Erwin。
