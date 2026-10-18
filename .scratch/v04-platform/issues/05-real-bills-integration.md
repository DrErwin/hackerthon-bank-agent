# 05：真实账单模块接入平台与纵向联调（替换契约形状桩）

Ticket ID: v04-platform/05
Type: 开发
Owner: Erwin
Directory: backend/app/api/
Status: in_progress（2026-10-18 阶段一〔L01〕经独立检查会话验收通过，见 Comments；阶段二未启动）
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01、P02、P03、P04](../spec.md)（真实数据链路下的端到端验收）
Verification: **分阶段验收（2026-10-16 PM 接受，见 Comments）**。阶段一（L01 起步）：消息入口 → 真实 `bills.summarize` 任务创建 / 等待 / 恢复、任务视图 `module=bills` + 真实载荷、银行取数三态透传。阶段二（L02/L03 追加，待 [v04-platform/12](12-contract-l02-l03-models.md) 与账单线 L03 就绪）：报告自动落库 → F21 读取 → F22/F24 明细导出与下载。与前端账单插槽、账单线 BF01—BF07 的纵向联调记录；报告与导出无秘密泄漏。命令与输出、联调记录链接记入本票 Comments；各阶段整条路径通过才算对应场景通过，局部接线不替代联调证据。
Blocked by: [v04-platform/10：规划入口支持第二业务模块](10-planner-second-module.md)（消息入口发起账单任务的前置）；安全侧读账口径与权限（[Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)，Ringo，转 Ringo）——账单 L01 本体已于 [PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131) 合入 main，原「账单公开能力可运行」前置的 L01 部分已满足；[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 记录缺口
Source issue: [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)

## 交付

1. 按可用性条件注册真实 bills 工厂，替换 `agent_platform/bills_stub.py` 的桩（桩保留为测试替身 / 降级路径，不删除、不作为生产默认）。**注册口径是「全有或全无」**：`ApiService` 装配时只在注册表里没有任何 `bills.*` 能力时才挂桩（`service.py:64-67`），真实模块一旦注册、桩整体让位——只注册部分能力时其余能力不会被桩补上；注册前须把 [modules/bills/manifest.py](../../../backend/app/modules/bills/manifest.py) 的 owner / version / 能力声明统一成真实一份。**分阶段口径（2026-10-16 PM 接受）**：L01 最小切片先行注册＝桩整体让位，`bills.detect_anomalies` / `bills.generate_report`（L02/L03）会从 `public_catalog()` 消失（不再是桩的三能力形状）——这是接受的阶段状态而非缺陷；L02/L03 就绪后追加注册。
2. 真实账单任务：任务视图 `module=bills` + 真实载荷、报告自动落库与 `report_ready` 事件端到端验证（票 04 接线在真数据下的确认；报告与 `report_ready` 属阶段二，L03 就绪后验收）。
3. 纵向联调：与前端账单插槽（frontend-complete/01）和账单线 BF01—BF07 联调，证据并入 [v04-bills/02](../../v04-bills/packages/02-v04-acceptance.md) 联合验收。
4. [Issue #122](https://github.com/DrErwin/hackerthon-bank-agent/issues/122) 的三处接缝已按一票一目录**提前单独收口**（[06](06-sse-event-payload-union.md) 契约 / [07](07-export-task-module-and-event-payload.md) api / [08](08-harness-resume-parsing.md) agent_platform，2026-10-14）；本票保留**真数据下的复验**：真实账单任务触发等待类交互时确认 resume 可推进、第二模块 `task_updated` 带真实载荷、导出任务归属 `bills`。
5. 同步更新 `backend/app/api/test_app.py` 中依赖桩三条能力形状的断言（桩让位后这些断言的语境变化），保持生产装配测试与分阶段注册口径一致。

## 边界与依赖

- 不在本票：账单业务实现与评测（周恩宇，[v04-bills/01](../../v04-bills/packages/01-bills-backend.md)）；前端页面实现（梁爽/六水）。
- 前置未满足时保持 `blocked`；平台侧接口（F21—F24、模块注册点 `register_module`）已就绪，可先做接线准备与非真数据（测试替身）验证。
- **能力名对账（票 07 审查提出）**：`bills.export_details`（敏感导出任务用的能力名）没有契约或 manifest 依据、注册表里查不到；导出任务在 `continue_task()` 处被 `export_for_task()` 短路、不进 harness，因此今天无需注册。本票须明确对账方式——真实模块登记同名能力，或与 API 侧改名对齐；并保持导出任务与 harness 恢复路径分离（任何把导出任务引入 harness 的改动都会因该能力未注册而失败）。

## Comments

- 2026-10-13：v0.4 盘点发现"真实账单模块接入"无归属票（票 03/04 只交付注册点与契约形状桩），登记 [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 并建立本票；前置=账单公开能力可运行。
- 2026-10-14 平台侧解封核对与 checkpoint：账单线票 03 的两个 `Blocked by` 事实上已满足——[Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91) 于 10-11 关闭、统计内核 PR #92 于 10-13 合入；但 `backend/app/modules/bills/` 至今只有私有内核与空清单（无 L01 注册入口），台账停在 10-11。平台侧已发解封通知（[Issue #123 回帖](https://github.com/DrErwin/hackerthon-bank-agent/issues/123#issuecomment-6150429852)），F21—F24、`register_module`、module/载荷/事件接线均已就绪。**10-16 checkpoint**：若 L01 仍不可运行，平台侧按降级口径推进（测试替身级接线 + 证据降级）并把延后如实写入版本文档，不再等待。
- 2026-10-14 本票保留的真数据复验范围按三票提前收口后的状态更新（见交付 4 与边界）；#122 关闭后若有真数据下的新发现，按一票一目录另开票。
- 2026-10-14 **前置准备（未解封状态下的测试替身验证，票面边界允许）**：新增两条用例守住交付 1 的可用性条件（[PR #129](https://github.com/DrErwin/hackerthon-bank-agent/pull/129) squash `2f8c0a0`）——①装配前注册账单工厂（测试替身代 `bills.test_report`）时，桩整体让位且任务由该工厂服务（`module=bills`、`BillReport` 载荷、F21 可读）；②默认装配必须挂上降级桩并由桩服务任务（`message == STUB_MESSAGE`、`data is None`）。**三种变异全部被杀**，含双轴审查发现的**存活变异** `bills.`→`transfer.`（该写法下桩会在生产里静默消失而全量仍绿——正文原先把它当等价变异，已更正）。证据：api 65 passed、后端全量 535 passed + 模拟银行 14 passed、CI 绿；生产路径 `service.py` 零改动。
- 2026-10-14 **解封第一步（待账单线接口冻结时执行）**：把公开能力的注册形态定死——按真实 owner/version 与非空能力清单（L01—L03，并对账 `bills.export_details`）替换 [modules/bills/manifest.py](../../../backend/app/modules/bills/manifest.py) 的空清单，并明确由部署工厂（`BANK_RUNTIME_FACTORY` 指向的 `build_runtime`，见 `transfer_runtime.py` 的转账注册点）在 `ApiService` 装配前调用 `registry.register_module` 完成注册。在此之前本票保持 `blocked`。
- 2026-10-16 **口径修订（承接 [PR #131 合并与三轴审查](https://github.com/DrErwin/hackerthon-bank-agent/pull/131#issuecomment-6198615597)）**：账单 L01 最小切片已合入 main（`85a119d`，`manifest.py` 已是真实非空清单），**PM 接受最小切片分阶段接入**——本票验收口径由「L01—L03 一起上」改为分阶段（L01 先行；L02/L03 追加），票面 Verification / 交付 1 / 交付 5 已按此修订。解封前置相应改为：[v04-platform/10](10-planner-second-module.md)（规划入口，否则 L01 注册后也无法从消息入口发起）+ 安全侧读账口径（[Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)，Ringo）。同日补拆平台票 [10](10-planner-second-module.md) / [11](11-audit-outcome-denial.md)（审计 outcome 缺陷，修复前不得用 outcome 证明读取成功）/ [12](12-contract-l02-l03-models.md)（L02/L03 公共模型，对应 [Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132)），账单线返修票 [v04-ethan-bills-backend/08](../../v04-ethan-bills-backend/issues/08-l01-rework-consistency.md)、[/09](../../v04-ethan-bills-backend/issues/09-module-dedup-test-coverage.md)（[Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)）。
- 2026-10-18 **独立检查会话验收（PM 授权代查，非 Owner 自审；检查基线 main `1b52ffb`，只认代码与实测）：阶段一（L01 分阶段口径）通过**。前置全部满足（票 10 `15cf0ad`、#137 临时口径回帖、L01 返修 `e7e7b8f` 均在谱系内）。检查中按授权代做两张 PR 并合入：
  - [#143](https://github.com/DrErwin/hackerthon-bank-agent/pull/143)（security 白名单，squash `81345b5`，**PM 代行、Ringo 未参与本人审查**）：`_permissions` 增 `bills.read`、`_private_tools` 纳入两条冻结声明、`_capabilities` 纳入 `bills.summarize`；gate 逻辑零改动；变异 3/3 杀 + 六字段冻结常驻断言；`app/security` 48 passed。
  - [#144](https://github.com/DrErwin/hackerthon-bank-agent/pull/144)（agent_platform 真工厂接线，squash `c10ba00`，**PM 授权代行、Owner 未参与本人审查**）：`build_runtime` 装配前 `register_bills`（真模块注册=桩整体让位，`public_catalog()`=transfer+bills.summarize；无注册仍挂桩，降级路径保留）；每任务新建 SecurityGate（`reads.py` 重复注册守卫，连续两任务用例+共享 ToolRegistry 变异即红）；`risk_facts` 对非副作用工具先回读侧 fixture；`security.decided` 经 trace 留痕。变异 3/3 杀；后端全量 **616 passed**、CI 绿；合并树=已测树（`ddae5a9`）。
  - **交付 5**：`api/test_app.py` 桩断言无需改（PR #129 的桩让位/挂桩两用例在全量中仍绿，默认装配语境未变）。
  - **阶段一端到端（真实 GLM 规划 `glm-5.3`、真实 gate、真种子银行，无 planner/风险策略替身；固定 worktree 于 `c10ba00`）**：消息「帮我查一下今年9月所有账户的账单」→ 真实模型产 `bills.summarize` 提案 → 任务 `module=bills` → 月份等待（本月/上月/前两个月）→ 选「上月」→ **succeeded**（`transaction_count=15`、`consumption_gross_fen=576100`、账户 `A1+A5`）；**两次独立运行结果一致**；**非种子银行写=0**（零资金动作）；事件流 `task_updated`/`interaction_required` 带 `module=bills`；审计：`tool.started`/`tool.finished` 5 对成对（bills）、`security.decided`×10 全 allow、`recovery.checked`+`task.transition(succeeded)`、无验证码原文。恢复路径（等待→选择→成功）另由 #144 用例（月份+账户两跳）覆盖。
  - **已知缺口（不阻塞阶段一）**：① 读路径 `audit_evidence` 仍整包 dump 银行事实（`reads.py:96-99,112-117`），与 #137 临时口径（摘要/引用式）不符 → 归 `modules/bills`（周恩宇）另票实施；② 阶段二（报告落库→F21→F22/F24、L02/L03）未启动；③ 前端账单插槽与 BF01—BF07 纵向联调未启动；④ `bills.export_details` 对账维持票面结论（导出不进 harness，阶段二再定）。
  - 代行记录：PM 授权代行、票 05 Owner（Erwin）与 Ringo 均未参与上述代做改动的本人审查；本条为验收事实核对，**非安全专业结论**；回归后复核，长期规则不变。Status 置 in_progress（阶段一已验收、阶段二未启动）。
