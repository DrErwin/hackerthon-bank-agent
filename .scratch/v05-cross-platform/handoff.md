# 第一个交付包：执行交接

最后更新：2026-10-24。包负责人 Erwin 已明确接包并授权拆票；票 01 后续已指派本聊天准备[公共约定裁定稿](01-decision.md)；其他票的实施交给其另行指定的执行者，本聊天未启动模型或业务代码实现。

交付包：[v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)。[工作规格](spec.md)与九张独立票已细化，沿用已批准编号和目录边界，不重复建票。

## 1. 九张票及推进顺序

| 正式票 | 单一实施目录 | 直接前置 | 交付结果 |
|---|---|---|---|
| [v05-cross-platform/01：公共模型落地](issues/01-public-models.md) | contracts | 无实施前置票；先准备准确契约差异并取得所需确认 | 各模块使用同一套合法输入、结果和父子交互约定 |
| [v05-cross-platform/02：任务关系与安排记录持久化](issues/02-durable-task-relations.md) | storage | [v05-cross-platform/01：公共模型落地](issues/01-public-models.md) | 重启不丢任务，两个计划不能重复安排同一份资金 |
| [v05-cross-platform/03：Harness 受控子任务衔接](issues/03-child-task-dispatch.md) | agent_platform | [v05-cross-platform/01：公共模型落地](issues/01-public-models.md)、[v05-cross-platform/02：任务关系与安排记录持久化](issues/02-durable-task-relations.md) | 各单项业务能等待、继续和恢复，确认归属正确 |
| [v05-cross-platform/04：联动任务与子交互 API](issues/04-parent-child-api.md) | api | [v05-cross-platform/03：Harness 受控子任务衔接](issues/03-child-task-dispatch.md) | 页面操作准确落到当前业务，刷新/恢复状态一致 |
| [v05-cross-platform/05：联动主入口及现有业务装配](issues/05-cross-runtime-wiring.md) | agent_platform | [v05-cross-business/01：减支编排和共用计划骨架](../v05-cross-business/issues/01-expense-reduction.md) | 自然目标进入真实联动模块，接上现有业务 |
| [v05-cross-platform/06：生日银行数据与原子提交](issues/06-bank-order-freeze-storage.md) | storage | [v05-cross-platform/01：公共模型落地](issues/01-public-models.md) | 资金、订单与操作记录一起成功或失败，避免重复付款 |
| [v05-cross-platform/07：生日模拟银行与网关](issues/07-birthday-bank-services.md) | services | [v05-cross-platform/06：生日银行数据与原子提交](issues/06-bank-order-freeze-storage.md) | 真实模拟商品、订单、冻结、扣款、释放及原操作查询 |
| [v05-cross-platform/08：配送资料受控 API](issues/08-controlled-delivery-api.md) | api | [v05-cross-platform/02：任务关系与安排记录持久化](issues/02-durable-task-relations.md)、[v05-cross-platform/04：联动任务与子交互 API](issues/04-parent-child-api.md) | 配送原文通过专用入口使用，不进聊天和模型 |
| [v05-cross-platform/09：生日工具、权限与演示装配](issues/09-birthday-runtime-wiring.md) | agent_platform | [v05-cross-platform/05：联动主入口及现有业务装配](issues/05-cross-runtime-wiring.md)、[v05-cross-platform/08：配送资料受控 API](issues/08-controlled-delivery-api.md)、[v05-cross-business/03：生日编排及预算约束](../v05-cross-business/issues/03-birthday-orchestration.md) | 生日业务、资金安全门和资料引用真正接通 |

目录均位于 `backend/app/`，准确写入边界见各票。表中列直接前置，前序的依赖同样必须满足。票 05、09 需要其他包提供真实业务，不能要求执行者在平台目录替其实现。

先处理 01 的公共约定与模型，再推进 02→03→04。01 就绪后 06→07 可提前准备，但 02/06 同属 storage，涉及同一迁移时须协调顺序；04/08 和 03/05/09 也不要并行修改同一共享文件。只要不共享文件且无真实依赖，可以分别推进；不为并行而绕过目录和合入条件。

## 2. 当前的开始条件

- **已经完成**：Erwin 接包；本包规格、九票、输入输出边界、验证要求和依赖交接。
- **票 01 准备已完成**：[业务裁定稿](01-decision.md)与[字段/状态/兼容/样例详稿](01-contract-detail.md)中的 D1/D2 已于 2026-10-24 获 Erwin 确认；字段与兼容仍待契约流程确认，尚未生成生效公共模型，不需要重复另写同范围提案。
- **模型与代码开始前**：完成所涉公共约定确认及必要安全审阅；后序票还须有前置公开能力的合入证据。接包本身不等于批准所有契约细节。
- **尚未记录**：九张票各自执行者、代码/PR、局部验证、真实 E2E 和安全签核。由 Erwin 指派后在相应票登记，不把包负责人当成已经写代码的执行者。

本包外的前端、cross 业务、安全实现和专项/E2E 验证沿原包协作；未因 Erwin 接受本包而自动领取其他五包。

## 3. 可复制给执行者的指令

把下面的 `<完整票号>` 替换成上表中的实际票号再交给执行者：

> 请在 D:\hackerthon-bank-agent 阅读 AGENTS.md、docs/agents/delivery-workflow.md 和 .scratch/v05-cross-platform/handoff.md。Erwin 已接受“公共接缝与模拟银行”包，现指派你执行 `<完整票号>`。沿用现有规格和票，不重新拆一套。先核对票面依赖和公共约定的确认记录；没有满足前置时报告具体缺口，不擅自修改其他目录。满足条件后记录实际领取人，按单目录、一票一分支/PR 实现及验证，保护现有未提交文件。完成后报告改动、验证证据、PR/合入状态和仍缺的 E2E；不要将局部测试或 AI 审查写成整场景验收或真人安全签核。

这段是供 Erwin 转交的模板，本聊天没有发给任何人，也没有创建或启动其他任务。

## 4. 每张票回交时提供什么

1. 实际执行者、基线提交、前置票及其合入证据。
2. 本票目录内的实现、必要契约/用法说明、真实验证结果及未通过项。
3. PR 和审查/合入状态；若存在跨目录缺口，给出提供方与具体依赖，不夹带实现。
4. 向下游交付的公开入口、输入输出样例、恢复/失败行为；未知和未实现如实说明。

完整 E2E 仍由原联动验收包组织；本包不能因九张代码票交付就自行宣布三目标全部通过。

## 已确认业务规则对下游的要求

- D1：同一付款账户一次只办理一份已采用的联动资金安排；普通转账等应用内冲突支出也须核对，不能绕过。影响本组 02/03/05/07/09 和受控执行接缝；Ringo 核对既有执行器能否承接，若需改安全、转账或前端目录，由对应负责人补明确依赖。未知及未核实收尾不解锁，不自动排队执行。
- D2：实际目标已部分完成后停止，必要收尾核实后用既有 partially_succeeded 表示，保留停止原因；尚无实际目标完成时才可记取消。付款或释放未知、释放失败仍待处理。父子任务、API、业务和前端按此衔接，E2E 应覆盖已付款后停止及释放未知。
- 完整要求以 [PRD](../../docs/prd/06-跨场景联动-PRD-2026-09-23.md) 和[裁定记录](01-decision.md)为准。本次不解锁票 01 的代码依赖，不代其他包接包或代签安全审查。
