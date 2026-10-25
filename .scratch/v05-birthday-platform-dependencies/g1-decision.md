# G1 受控编辑入口：确认与验证等待态的 F10 分流

Status: decided — 2026-10-26，Erwin 授权执行对话按 v0.5 代行职责记录；**AI 记录，不等于 Ringo 本人签核**。
Owner: Erwin（v0.5 阶段统一负责）
Related: [平台规格 §4.1](spec.md#41-现行拒绝路径与契约裁定g1)、[本人裁定](../v05-control/birthday-owner-decision.md)（共同条件 3「入口只接受当前真实待办」）、[票 04](issues/04-api-edit-entry.md)、[票 03](issues/03-platform-edit-handoff.md)

## 1. 决定

采用规格 §4.1 的**建议 G1**：不新增端点，复用 F10 现有请求体，只在 Cross 当前确认/验证卡上增加**一个后端发布的受控编辑选项**。

- 请求仍只有 `request_id`、`interaction_id`、`selected_option_id`，`text` 必须为空；
  不接受客户端自报 `actor` / `editable` / `operation` / 候选 hash / 安全通过标记。
- 选项 ID 由后端发布并绑定：当前任务、执行项、原 operation/attempt、确认版本与当前交互；
  旧卡片、旧交互、其它模块的选项一律不认。
- 普通 F10 仍只答 `input`；普通 text / `provide_input` / 模型 revise **不进入**该分支。
  F15 仍只有 `approve` / `cancel`，编辑不等于资金批准，也不等于取消整个任务。
- 输出复用 `TaskView`：安全撤离与检查点发布完成后，同一 `task_id`、新 `task_revision`、新 `interaction_id`、`waiting_input`；
  抢先提交或结果未知时仍沿原操作显示核实状态，不假装已进入编辑。
- 不新增公共状态、权限等级或 `SecurityDecision` 枚举；复用 `allowed_actions` 现有值。

## 2. 按契约 §8 的变更性质与影响

- 性质：**改变 F10 的适用状态与暂停/恢复语义**，不是纯内部修复，也不是仅新增可选字段；
  本页记录按 §8「不兼容修改」路径处理，需契约负责人确认并定向通知受影响方。
- 影响方：`backend/app/api/`（实施，票 04）、`backend/app/agent_platform/`（票 03）、
  安全撤离依据的消费（票 02，只消费不扩权）、`backend/app/modules/cross/`（票 08，提供"进入原任务编辑"侧）、
  `frontend/`（票 02，页面文案与交互**另需本人走查批准**）。
- 旧代码是否仍可用：是——不带该选项的既有 F10 调用、普通 input、F15、转账 draft 与验证码路径行为不变；
  新选项只在后端明确发布后才可能被选中。
- 契约正文的修订记录（`docs/contracts/公共契约-2026-09-23.md` 顶部修订区）在票 04 的 PR 中一并补登，
  本条是其先行裁定依据，不替代 PR 内的契约文档更新。

## 3. 安全与验收边界

- 后续全部按 [G2-B 胜序](verification-authority.md)：银行库先权威判定旧挑战能否退役；
  安全 02 无 claim 才签发可编辑依据；无法证明先后一律暂停编辑。
- 编辑入口不放宽资金动作：新方案仍需新确认、必要新验证与新 claim；不撤单、不退款、不追加冻结、不换账户、不自动加预算、不改 #160。
- 撤销/终态/旧会话/越权/异参全部按既有拒绝；`needs_attention`、`partially_succeeded` 不等于可编辑。
- 真实 E2E、页面验收、200%/读屏与最终安全/体验接受仍由本人另行安排。

## 4. 记录口径

本决定由 Erwin 在 v0.5 阶段授权执行对话代行确认并记录（AGENTS.md「v0.5 阶段执行例外」）；
不写成 Ringo 本人审查或签核。页面上的新选项文案与位置属用户可见改动，须本人页面走查另行批准。
