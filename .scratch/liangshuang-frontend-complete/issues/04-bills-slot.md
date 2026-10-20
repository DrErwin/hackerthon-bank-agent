# 04：账单业务插槽

Ticket ID: liangshuang-frontend-complete/04
Type: 开发
Owner: 梁爽
Directory: frontend/
Status: done（v0.4。插槽已按公开契约展示汇总、明细、异常和报告；**真实接口联调已由 PM 侧（AI 代执行）完成并随 [PR #199](https://github.com/DrErwin/hackerthon-bank-agent/pull/199) squash 合入 main `1242633`**。前置已解除：平台 [PR #178](https://github.com/DrErwin/hackerthon-bank-agent/pull/178) `2791e40`；安全白名单 [PR #184](https://github.com/DrErwin/hackerthon-bank-agent/pull/184) `3f9996c`。审查修复 3 项、1 项按 PM 决定保留，遗留清单见 Comments）
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: [FE-02、FE-03、FE-06](../../frontend-complete/spec.md)
Blocked by: [liangshuang-frontend-complete/02](02-frontend-shell.md)；真实联调依赖 `v04-bills/01` 发出可调用公开能力信号
Verification: 用契约形状 stub 走通入口、明细与报告；公开能力可调用后核对真实响应、失败与恢复，不把 stub 通过记为真实联调。

## 交付与验收

- 在同一底盘接入账单三类能力入口、明细和报告卡片。
- 报告金额、分类、异常线索与状态只展示账单公开能力返回。
- 公共接口未就绪时只使用明确标注的契约形状 stub，不发出可联调完成信号。
- 缺少必要数据格式时提出契约变更，不在前端自定义平行 schema。

## Comments
- 2026-10-20（梁爽）：账单插槽接到 `/v04`。`module=bills` 时按公开返回区分：`SpendingSummary` 汇总、`BillDetails` 明细、`AnomalyResult` 线索、`TransactionCandidates` 定位、`BillReport` 报告卡片。金额、分类、线索和口径只用服务端字段。报告卡片不含原始明细。本机没有 local-demo 密钥，契约测试不能当成真实联调。
- 2026-10-20（PM 01:45 撤回顺延，AI 代填）：本票**留在 v0.4 完成**。同日 01:41 记录的「顺延 v0.5 / v0.4 不做 stub 切片」作废。前置不变：`bills.generate_report`（L03）需平台注册 + 安全白名单收录 `REPORT_MANIFEST`；在前置解除前只做明确标注的 stub，不发出可联调完成信号。
- 2026-10-20（AI 代填，PM 授权代做/通知）：**两个硬前置已全部解除**——① 平台注册 L03（[PR #178](https://github.com/DrErwin/hackerthon-bank-agent/pull/178) squash `2791e40`，`public_catalog()` 已含 `bills.generate_report`）；② 安全白名单收录（[PR #184](https://github.com/DrErwin/hackerthon-bank-agent/pull/184) squash `3f9996c`，安全侧独立冻结快照，`policy_version=v04-local-demo-read-2`，[Issue #177](https://github.com/DrErwin/hackerthon-bank-agent/issues/177) 已关闭；PM 代行、非 Ringo 本人审查，真人安全签核仍缺，不阻塞本票）。真实 local-demo HTTP 栈端到端实测：L03 任务 `succeeded`、`module=bills`、返回 `report_id`（改动前为「202 但不建任务」）。本票可开始**真实联调**、不要再留 stub；阶段二剩余（报告落库→F21→F22/F24 的验收、前端插槽契约对齐）照平台/前端线继续。
- 2026-10-21（AI 代执行 · 真实接口联调与审查处置）：**真实 local-demo 栈联调通过**（真实后端 + GLM Coding Plan `glm-5.3` + 模拟银行，非 contract-demo/stub）：汇总、餐饮明细、转账明细（打码账号原样）、异常（真实命中夜间规则 + 数据不足中文原因）、月账单报告（不含原始明细、无演示字样）共 5 场景 / 98 项断言与 API payload 逐字段一致，`VERDICT=PASS`；证据 [2026-10-21-real-api-bills-slot.md](../evidence/2026-10-21-real-api-bills-slot.md)。PR #199 rebase 到 main `9b27d5b` 后 `npm test` 38 passed / `npm run build` 通过，squash 合入 main `1242633`（自动删除 head 分支）。
- 2026-10-21（AI 双轴审查 → PM 决定）：审查结论「有条件可合」。**已修**：① 交易行按 `nature` 显示消费/退款/转账/利息（原退款会显示成「收入」）；② 数据不足原因由机器码映射中文、未知统一「这次没能核对」、删除「银行没有返回原因」错误归因；③ 有符号金额统一 `-¥300.00` 形式。**未采纳（PM 2026-10-21 00:00 决定）**：异常卡在仅有数据不足时仍显示「没有发现需要留意的交易」+ 成功色（与契约「数据不足 ≠ 未发现」不一致），保留现状、记录在案。
- 2026-10-21（遗留清单，不阻塞本票，后续单开）：明细行补 `channel`（渠道）展示；报告卡导出/下载入口（需按安全门单独验证）；`contract-demo` 演示模式示例句含账单句式但 stub 后端只支持转账；报告卡行数偏多与术语适老化精简；`isSummary`/`isBillReport` 形状校验补 `scope`、`statistical_days`；平台 `TaskView` 缺载荷判别字段（按公共改动流程另提）；部分完成状态、未知枚举兜底、时间字段集中、报告卡与气泡文案重复等低优先项。