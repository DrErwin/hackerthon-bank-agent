# 交付包 01：v0.4 底座、Agent 与模拟银行（API / Harness / 银行接缝）

Status: in_progress（2026-10-13 Erwin 本人接受；同日双轴审核通过并完成拆票，实施票见 [issues/01—12](../issues/)。01—04、06—09 已 resolved；**2026-10-16 起平台侧在办：票 05（分阶段口径）+ 补拆 10/11/12**，见下「验收证据索引」与 Comments）
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

## 验收证据索引（滚动，2026-10-14 建档）

> 用途：10-20 收口时逐条复核，也供 10-16 checkpoint 判断"平台侧还剩什么"。命令统一在 `backend/` 下用仓库 `backend/.venv`（含全部依赖）执行；主线基线 `83de47f`：后端全量 **535 passed**、模拟银行评测 **14 passed**，各 PR 的 CI（Repository checks，含后端全量与模拟银行）绿。

| 场景 | 票 | 可复核证据（用例 / PR） | 状态 |
|---|---|---|---|
| P01 账单任务创建、等待、恢复 | 04 / 05 / 08 | `test_bills_task_wires_module_payload_and_report_ready`、`test_installed_bills_module_replaces_the_contract_stub`、`test_default_assembly_installs_the_contract_stub`（api）；`test_waiting_second_module_task_resumes_along_its_own_payload`、`test_waiting_second_module_task_recovers_into_a_new_session`（agent_platform） | **已验（测试替身级）**；真实账单任务待票 05 |
| P02 前端按 `module` 选插槽、双场景互不串台 | 04 / 06 / 07 | 契约侧 `test_task_updated_event_carries_the_second_module_payload`（整份账单载荷 + JSON 往返 + 事件层非法 module 拒绝，PR #126）；api 侧事件带载荷与 `module=bills` 断言（PR #128）；转账 `module=transfer` 回归用例 | **平台侧已验**；前端插槽实现归 frontend-complete/01（其 `slots.resolve` 用例见前端目录） |
| P03 报告读取 F21 | 01 / 09 | `test_f21_returns_the_report_card_to_its_owner_only`（本人可读、管理员 404、响应无明细行，PR #115）；卡片产物纳入票 09 的秘密扫描（`e46522a`） | **已验（受控报告）**；真实账单报告待票 05 |
| P04 卡片 / 明细导出 F22—F24 | 02 / 07 / 09 | 导出链路用例组（明细再验证、取消、重发、会话变化、越权 404、未就绪 409，PR #119）；`test_f22_details_export_requires_fresh_verification` 现含完成态 `module=bills` 与跨会话必经导出路径断言（PR #128）；[票 09](../issues/09-export-secret-scan.md) 补全产物 + 全表验证码扫描（`e46522a`） | **已验（平台链路级）**；验证口径由 PM 2026-10-13 代行豁免 Ringo 审批（非本人审查，已记录） |
| P05 账单取数与失败三态 | #91 / 05 | #91 四票（PR #97/#98/#100/#102）B08 取数 + 三态语义；`evals/mockbank` 14 passed；底座只验管道与三态透传 | **银行接缝已验**；账单任务在真数据下的三态透传待票 05（结论口径归账单线 BF03/BF06） |
| P06 契约受理与联调 | 全组 | 受理留痕：#113/#114（`TaskView.module` + 报告/导出模型）、#122 三处接缝（PR #126/#127/#128，§8 轻量确认档登记）、#121（F35 挂 v0.5）、#123 + 票 05；跨线通知留痕：[Issue #123 回帖](https://github.com/DrErwin/hackerthon-bank-agent/issues/123#issuecomment-6150429852)、[Issue #89 评论](https://github.com/DrErwin/hackerthon-bank-agent/issues/89#issuecomment-6150599086) | **受理流程持续有效**；跨线联调证据待票 05 解封后进 [v04-bills/02](../../v04-bills/packages/02-v04-acceptance.md) |

**验收标准 2「无验证码或秘密泄漏」的证据归属**：[票 09](../issues/09-export-secret-scan.md) 的 `test_export_secrets.py` 跑完整条明细导出链路后，扫描**全部对外产物**（创建 / 验证与状态回执、任务视图、验证历史回放、F21 卡片、CSV、SSE 事件）与**平台库全部用户表**——含导出链路写入的 `api_exports` / `api_reports` / `api_tasks`（v0.3 的扫描名单恰好漏掉这三张），并对三张表加最小行数断言避免在空表上静默通过；两半扫描各用一次注入检验证明有效（库侧注入报出 `api_requests` 行、响应侧注入报出 `verify`）。验收标准 2 的其余子项由票 01/02 既有用例覆盖、本票不重复：本人范围校验（`test_app.py` 报告 owner / 管理员 404、导出越权 404）、未过验证不给内容（明细下载 409）、下载路径受控（路径校验与就绪 409/404）。

**当前缺口（一句话，2026-10-16 更新）**：账单 L01 已随 [PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131) 合入 main（行为中性——生产装配仍挂桩，`register_bills` 只被测试调用）；PM 接受**最小切片分阶段接入**（L01 先行；L02/L03 追加），票 05 解封前置 = [票 10](../issues/10-planner-second-module.md)（规划入口，[Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134)）+ 安全侧读账口径（[Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)，Ringo）；另有平台缺陷票 [11](../issues/11-audit-outcome-denial.md)（审计 outcome，[Issue #135](https://github.com/DrErwin/hackerthon-bank-agent/issues/135)）与契约票 [12](../issues/12-contract-l02-l03-models.md)（L02/L03 公共模型，[Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132)，解锁账单线 L02/L03 与 F21—F24 报告链路）。

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
| [10](../issues/10-planner-second-module.md) | `backend/app/agent_platform/` | 规划入口支持第二业务模块（真实 planner 可产账单提案；2026-10-16 补拆） | [Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134) |
| [11](../issues/11-audit-outcome-denial.md) | `backend/app/agent_platform/` | 拒绝/失败路径审计 outcome 修复 + 回归断言（2026-10-16 补拆） | [Issue #135](https://github.com/DrErwin/hackerthon-bank-agent/issues/135) |
| [12](../issues/12-contract-l02-l03-models.md) | `backend/app/contracts/` | L02/L03 公共契约模型落地（冻结 §5.3；2026-10-16 补拆） | [Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132) |

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
- 2026-10-14 三票当日合入并置 resolved（06 [PR #126](https://github.com/DrErwin/hackerthon-bank-agent/pull/126) `91ddc4a` / 08 [PR #127](https://github.com/DrErwin/hackerthon-bank-agent/pull/127) `3613ce0` / 07 [PR #128](https://github.com/DrErwin/hackerthon-bank-agent/pull/128) `77726a9`；各自双轴独立子代理审查〔AI 审查、非真人〕，08 的 P1 与全部 P2/P3 当日处置），[Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 关闭；同轮完成票 05 前置准备（[PR #129](https://github.com/DrErwin/hackerthon-bank-agent/pull/129) `2f8c0a0`：双向守住「真实模块替换桩」的可用性条件，三种变异被杀）。主线基线 535 passed + 模拟银行 14 passed。
- 2026-10-14 建档「验收证据索引（滚动）」：P01—P06 逐条对应票、可复核用例与状态，供 10-16 checkpoint 与 10-20 收口复核；当前缺口只有票 05（`blocked` 于账单线）。
- 2026-10-14 建[票 09](../issues/09-export-secret-scan.md)（[PR #130](https://github.com/DrErwin/hackerthon-bank-agent/pull/130) `e46522a`）补齐验收标准 2「无验证码或秘密泄漏」的证据：扫描全部对外产物（正文 + 响应头）与平台库（`application.sqlite`）全部用户表——含 v0.3 扫描名单漏掉的导出链路三张表，并加覆盖面/内容下限断言；注入 A/B 与反证 V1/V2/V3 证明两半扫描有效、三条静默通过路径已封。索引 P03/P04 行已回填，平台侧证据不再有已知缺口（主线基线 536 passed + 模拟银行 14 passed）。
- 2026-10-16 **承接 PR #131 合并与三轴审查结论（AI 审查、非真人）**：账单 L01 最小切片合入 main（squash `85a119d`），合并行为中性（生产仍挂桩）。三轴发现三条平台级拦路（规划入口产不出账单能力 / 生产安全策略不认账单读取 / 最小切片不覆盖 L02/L03 的 F21—F24 报告链路）与一处平台既有缺陷（安全拒绝被记成 `outcome=succeeded`）。据此：①票 05 验收口径改**分阶段**（L01 先行、L02/L03 追加；PM 接受，见票 05 Comments）；②补拆 [10](../issues/10-planner-second-module.md)（规划入口，[Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134)）/ [11](../issues/11-audit-outcome-denial.md)（审计 outcome，[Issue #135](https://github.com/DrErwin/hackerthon-bank-agent/issues/135)）/ [12](../issues/12-contract-l02-l03-models.md)（L02/L03 契约模型，[Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132)）；③安全侧读账口径与审计证据四项开 [Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137) 转 Ringo（不代签）；④账单线五项返修开 [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) 转周恩宇（v04-ethan-bills-backend/08、/09）。
- 2026-10-16 **[票 12](../issues/12-contract-l02-l03-models.md) 当日合入**（[PR #138](https://github.com/DrErwin/hackerthon-bank-agent/pull/138) squash `4ed5555`）：L02/L03 冻结 §5.3 模型落地（`DetectAnomaliesInput` 三态互斥等七模型，`app.contracts` 导出，命名与桩 schema_ref 对应）。双轴独立子代理审查（AI 审查、非真人）均判**可合**，变异 3 组 3 杀 0 活；P3 意见当日处置（`a70de72`：reason 显式、对照期校验抽助手、docstring 补 candidates；strict-Literal 按 KISS 放弃留注释）。contracts **53 passed**、后端全量 **596 passed**、CI 绿。账单线 L02/L03 两分支的公共模型前置解除。
- 2026-10-17 **[票 10](../issues/10-planner-second-module.md) 合入**（[PR #139](https://github.com/DrErwin/hackerthon-bank-agent/pull/139) squash `15cf0ad`）：规划入口支持第二业务模块——`capability_name` 进工具面（默认转账、转账行为不变）、提示词按 catalog 动态列举、前后置校验。双轴（Spec/Standards，AI 审查、非真人）均**可合**；Spec 独立核实"harness 无需改动"（票 03/08 已通用路由）；Standards 变异 2 杀 1 活（提示词行无自动化覆盖→留票 05/评测）。`agent_platform` **125 passed**、api 65 passed、全量 **601 passed**、CI 绿。[Issue #134](https://github.com/DrErwin/hackerthon-bank-agent/issues/134) 关闭；票 05 解封前置只剩 [Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)（安全侧读账口径）。[票 11](../issues/11-audit-outcome-denial.md) PR #141 审查在途。
