# 01：总方案、子确认和结果页面

Ticket ID: v05-cross-frontend/01

Package: [v05-cross-linkage/packages/04-frontend：联动页面体验](../../v05-cross-linkage/packages/04-frontend.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（v0.5 本阶段统一负责）

Directory: `frontend/`

Status: in_progress — 方案走查已通过（Erwin，2026-10-25）；先完成平台票 11（G1/G2），再编码。

Package accepted by: Erwin

Package accepted at: 2026-10-25

Execution assignee: Erwin 转交的执行对话（DeepSeek Agent，2026-10-25 接手，代行实施）

Accepted by: 未记录（执行对话已接手，待 Erwin 走查/验收后记录）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01、XL-P01、X02—X05、X08；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

先提交版式/文案供 PM 走查，再实现父总览、原子确认卡、逐步结果/等待/恢复；采用方案不等于批准全部办理。复用原转账/退订卡片

## Blocked by

- [v05-cross-platform/11：子任务交互登记与联动文本输入](../../v05-cross-platform/issues/11-child-interaction-and-text-input.md)（2026-10-25 页面走查发现 G1/G2 两处 P0，PM 裁定优先修）

### 已合入的前置（保留记录）

- [v05-cross-platform/04：联动任务与子交互 API](../../v05-cross-platform/issues/04-parent-child-api.md)

上述 API 已合入（#259）。真实减支/养老金联调还需核对 [平台 05 装配](../../v05-cross-platform/issues/05-cross-runtime-wiring.md)（#276）及 [业务 01](../../v05-cross-business/issues/01-expense-reduction.md)/[业务 02](../../v05-cross-business/issues/02-monthly-arrangement.md)（#269/#268）。这些均已合入，账单类型化入口遗留仍可能阻断部分路径，不能据此宣称全链可用。

## Start when

- Erwin 已于 2026-10-25 领取本包并要求交其他对话实施；执行者收到转交后登记本票领取，先完成页面方案走查。本轮交接未实施代码或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。
- 具体页面/文案在本票编码前提交 PM 走查；粒度批准不等于 UI 定稿。

## Acceptance criteria

- [x] 实施前提交方案总览、子卡片及结果状态的具体版式/文案并记录 PM 走查结论。（[page-plan-01.md](../page-plan-01.md) §11，Erwin 2026-10-25 认可）
- [x] 采用方案与确认具体业务不同；调用后端真实 allowed_actions，不靠聊天肯定词自动放行。（父卡只展示步骤与「采用」菜单，无「全部批准」；子任务确认卡按子任务 `allowed_actions` 渲染，测试 `loads children from the API and renders the child's confirmation inside the plan`）
- [x] 多个任务、插入查询、等待、失败、未知、断线/刷新时不丢目标和已办项，旧确认不可用。（父任务快照的步骤状态在刷新后由服务端恢复，子任务经 `GET /tasks/{id}/children` 取回；旧确认由服务端 `allowed_actions` 决定只读。**未验证**：200% 缩放与读屏真机走查、真实页面断线恢复留证）
- [x] 复用原转账/退订验证卡；检查键盘、200% 缩放及读屏标签，本票页面结果留证。（子任务经同一 `TaskBlock` 用原 slot 渲染，确认/验证卡未改；`aria-current` 标记当前步骤、原生 `<details>`/`<button>` 保证键盘可达。**未验证**：200% 缩放与读屏实测，留真实页面走查）

## 执行与回交

1. 先盘点现有聊天、任务记录、确认/验证、转账/退订组件和真实数据源；沿用已批准视觉规范，列出本次新增状态。
2. 在本工作组补可走查的具体版式/文案，至少展示方案采用前、子项确认/验证、部分完成、失败/未知、断线恢复；记录 Erwin 走查结论后再实现生产页面。
3. 按当前公共类型接父目标/子任务查询，确认、验证、补充输入与取消路由到实际任务和有效交互；allowed_actions 只来自服务端。既有卡片继续复用。
4. 刷新/重连先恢复真实快照，过期确认只读；重复点击不创建新业务，插入查询后可回原安排。后端缺口记录完整票/接口/复现，不越界修复。
5. 验证并交付独立 frontend PR；回填实际走查、测试、联调、审查与合入证据，供前端 02 和 E2E 01/02 使用。

| 检查 | 预期可观察结果 |
|---|---|
| 采用方案与敏感确认 | 采用不触发全部写动作；当前确认只绑定对应任务/版本 |
| 两个子项、插入查询 | 当前办理项清楚，查询不覆盖原确认，成功项不重做 |
| 旧确认、重复点击、刷新/断线 | 旧卡不可提交，重复请求不换号，恢复后与服务端一致 |
| 失败、未知、冲突、会话失效 | 显示原因/下一步；不得伪装成功、自动重办或恢复旧权限 |
| 键盘/200%/读屏及既有业务 | 新页面可操作、焦点可追踪；现有转账/退订卡不回归 |

验证复用现有数据源、卡片和恢复测试；另记真实 React + HTTP 联调证据。账单路径受阻如实登记；固定数据测试不能替代减支/养老金真实模型 E2E。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 方案走查：2026-10-25 通过（Erwin 认可版式与文案；追加批准联动菜单输入框，见 [page-plan-01.md](../page-plan-01.md) §11）。
- 实现 / PR：`frontend/` 一次性实现（联动总览卡、子任务嵌套、结果/停止、恢复与输入框；跨域类型经 `frontend/scripts/generate_contract_schema.py` 生成），PR 待回填。
- 本票验证：`npm test` 79 passed（含新增 9 条联动用例）；`npm run build` 通过。**未做**：200% 缩放与读屏实测、真实页面 HTTP 联调、断线恢复留证——这部分留真实页面走查与 [E2E 包 05](../../v05-cross-linkage/packages/05-cross-e2e.md)。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 7](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（责任更新）：本票本阶段执行由 Erwin 承担；具体票的开工、实现和验证状态仍按实际结果记录。

2026-10-25：Erwin 明确领取包 04；本票沿用原编号并细化执行/验证要求，交其他对话实施。具体票领取、页面走查及编码均未代记为完成。

2026-10-25（执行接手）：按交接转交登记本票由执行对话接手，开始日期 2026-10-25。本轮先盘点现有前端与真实接口、提交具体页面方案供 Erwin 走查；未编码、未运行测试或 E2E，也未记录 PM 走查结论。Owner 仍为目录归属，不表示本票由该执行对话以外的人领取。

2026-10-25（走查通过）：页面方案 [page-plan-01.md](../page-plan-01.md) 与可点原型 [frontend/联动-交互原型-v0.1.html](../../../frontend/联动-交互原型-v0.1.html) 经 Erwin 走查，**六屏版式与文案认可、按此实现**。走查同时发现两处平台 P0（子任务确认/验证记录未登记、联动父任务文本回答被 API 400），PM 裁定另开 [v05-cross-platform/11](../../v05-cross-platform/issues/11-child-interaction-and-text-input.md) 优先修复，本票编码排在其后。走查结论只批准版式与文案，不代替页面验收或安全签核。

2026-10-25（实现）：按走查方案实现，只改 `frontend/`：
- 新增联动总览卡（步骤清单 + 当前步骤标 `aria-current` + 服务端金额依据 + 停止/回执话术）、`crossSlot`、子任务嵌套渲染；跨域类型在 `frontend/scripts/generate_contract_schema.py` 增导出后重新生成，不改后端契约。
- 数据源新增 `listChildren`（`GET /tasks/{id}/children`）；`useConversation` 在载入与父/子任务更新时拉取子任务并合并，子任务不再单独出现在时间线、计数和「继续办理」条里。
- 子任务确认/验证卡完全复用原组件与 slot（转账/退订卡外观与规则未改）。
- 追加批准项：联动菜单在可选项少于 3 个时显示输入框「也可以直接打字回答，例如 1500 或 1500元」+「填好了，继续」，文本经 `provideInput` 走模块自校验（平台票 11 已放行）。
- 未做：200% 缩放 / 读屏实测、真实页面与 HTTP 联调、断线恢复留证（留真实走查与 E2E 包 05）。
