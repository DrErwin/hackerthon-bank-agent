# 前端 02 开工清单（生日页面，批准后执行）

Status: ready-to-start — 后端八票已合入（2026-10-26），本清单只做只读盘点，**未改 frontend/**，等本人走查 D01—D11 批准后按此开工。
Owner: Erwin（v0.5 统一负责）
Related: [页面方案](page-plan-02.md) · [走查脚本](walkthrough-02-2026-10-26.md) · [前端票 02](issues/02-birthday-ui.md) · [生日可交付事实](../v05-birthday-platform-dependencies/delivery-handoff.md)

## 1. 现有前端结构（盘点结论）

- 入口为完整 shell：`src/shell/`（`ShellApp.tsx`/`AssistantPage.tsx`/`useConversation.ts`/`realDataSource.ts`）；旧 `src/TaskCard.tsx` 为另一套渲染，开工前先确认主入口未引用（若被引用需评估是否同改）。
- 交互卡：`shell/components/ConfirmationCard.tsx`（确认）、`VerificationCard.tsx`（验证码/人脸）、`TaskBlock.tsx`/`CrossPlanCard.tsx`（联动计划与子任务）、`StatusCards.tsx`（普通输入选项）。
- 数据层：`shell/useConversation.ts`（提交/恢复/SSE/错误文案）+ `shell/api/realDataSource.ts`（HTTP/SSE 适配）+ `src/api.ts`（ApiError）。
- 联动视图映射：`shell/cross.ts`（scenario/step 文案）、`shell/cross-plan.test.tsx`。

## 2. 与本票直接相关的三处真实缺口（后端已就绪，前端未消费）

1. **确认/验证卡不渲染后端发布的选项**：`ConfirmationCard` 只画「确认/取消 + extraActions」，`VerificationCard` 只画验证码/人脸/重发；后端 04 把「修改尚未提交的部分」选项放在 `interaction.options` 里发布，前端必须按 option id 渲染并走 F10（`selected_option_id`，`text` 为空）。**不得按文案匹配**。
2. **错误体 `reason` 未消费**：后端 04 为受控编辑新增公共 `reason`（用于「刷新后重试」/「沿原任务核实，勿重复提交」/「原任务结果待核实」）。`api.ts` 的 `ApiError` 目前只有 message/status；需读 problem body 的 `reason` 并在 `errorText()` 按码分档（403/404/409×4/503）。
3. **生日结果的结构化事实展示**：`CrossTaskView.steps/order_id/payment_status/冻结·消费·释放金额` 已在后端 05/08 提供，`CrossPlanCard` 需按计划展示（含「追加/引用」两类），不再只显示 message 文本。

## 3. 开工顺序（批准后）

1. `api.ts`/`types.ts`：`ApiProblem` 增加可选 `reason`；`ApiError` 透出；`errorText()` 分档文案（与后端口径一致，勿自造新码）。
2. `ConfirmationCard`/`VerificationCard`：当 `interaction.options` 非空时按选项渲染（label 原样、id 后端给）；点击 → 走 `useConversation` 的 F10 提交（`selected_option_id`，不带 text）；成功后以返回 TaskView 替换当前卡（同 task、新 revision、新 interaction），失败按 §2 分档展示。
3. `ChooseEdit` 后的新普通 input 卡：沿用既有 `StatusCards`/菜单渲染，不新增组件族；数量输入使用受控数字输入（正整数、上限校验在前端只做提示，最终以服务端拒绝为准）。
4. `CrossPlanCard`：生日步骤/订单/付款/冻结/释放结构化展示，金额来自服务端，不由前端推算；未知/待核实单独呈现，不显示「已完成」。
5. 测试：`npm test`（组件级：选项渲染、F10 提交、409/503 文案、重放不重复、SSE 事件去重）+ `npm run build`；页面走查/200%/读屏留本人安排。

## 4. 直接依赖的后端契约（已合入，勿改）

- 04：F10 受控编辑分流、成功返回同 task 新 revision/interaction、**已写历史与 SSE**（事件 id 由 `edit_ref` 稳定派生）；错误映射见 `backend/app/api/README.md`。
- 03/08/09：编辑后继续会新 attempt/新确认；同参延续在平台未就绪时 fail-closed 停驻（页面应显示「稍后再试（保留现状）」选项，而不是当成失败/取消）。
- 走查未批准前不得改页面文案/版式；本清单不包含任何页面文案定稿。

## 5. 明确不在本票

真实 E2E、200%/读屏/真机验收、模型对话质量、跨会话恢复接线、普通输入发布断点的 API 自动恢复（前端只按服务端返回呈现）。
