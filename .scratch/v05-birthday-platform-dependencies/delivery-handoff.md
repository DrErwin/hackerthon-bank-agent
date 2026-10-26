# 生日功能：可交付事实与交接缺口（2026-10-26）

Status: 后端已交付、页面待本人走查；真实 E2E 与最终接受未做。
Owner: Erwin（v0.5 统一负责）；执行：Erwin 授权执行对话（AI 代理）。
Related: [系列执行记录](../../v05-control/birthday-series-2026-10-26.md) · [页面走查脚本](../../v05-cross-frontend/walkthrough-02-2026-10-26.md) · [前端票 02](../../v05-cross-frontend/issues/02-birthday-ui.md) · [E2E 设计](../../v05-cross-e2e/spec.md)

## 1. 现在真实可用的能力（已合入 main，均有局部/真实组合测试）

| 能力 | 现状 | 证据 |
|---|---|---|
| 生日下单真实数量 | 计划项带稳定 `item_id` 与 `quantity`，`CreateOrderInput` 真传数量、行小计=单价×数量；同款替代是新 item/新订单/新付款 | 01 PR #306；`app/agent_platform/test_birthday_quantity_items.py` |
| 提交前方案存档不可覆盖 | 初始/普通/编辑状态都由 05 首份封存 + 平台同次严格 CAS 发布；旧 `put/put_writes` 不能覆盖已封存 namespace | 05 PR #307；03 PR #310 |
| 等确认/等验证码时修改未提交部分 | 受控编辑入口 → 安全原子撤离（无 claim 才放行）→ 银行侧旧挑战封存（先撤离则之后超时不拖停新方案）→ Cross 准备隔离候选 → 发布新 input | 02 #309、06 #308、03 #310、04 #311 |
| 改数量/移除/替换 | 由受控编辑进入后给新普通 input；改后重算、冻结前重新采用、冻结后重新确认；旧确认不能批准新参数；超额/非法量/空方案零资金写入 | 08 PR #312 |
| 改价必须重新确认 | 价格变化不再直写行后提交，而是重算→bump plan_revision→重走 order_check→新确认→用户批准才提交 | 08 PR #312 |
| 改完继续办 | 同参数会生成新 attempt/新 operation（旧 attempt 永不复用、历史可查）；三卡均新确认 | 09 PR #313 |
| 不误伤旧事实 | 已付/已建未付/明确失败/未知均保留；未知沿原号核实；不改写历史订单/付款；不撤单退款、不追加冻结 | 02/03/08 各票测试 |
| 编辑失败不废掉已批准付款 | `pending_proof` 期间旧动作仍按原规则可被领取；claim 胜即置 conflict、seal 永不能签发 | 02 PR #309（M1 修正） |
| 同参延续不整单收口 | 平台暂拒时 Cross fail-closed 停驻，「稍后再试」保留冻结与已发生事实、释放 0（修复前会整单取消并释放 800/601 元） | 08 PR #312 |

合入后测试口径（2026-10-26，main `6a6526e`）：`agent_platform` **376 passed / 13 skipped**、`modules/cross` **120 passed**、`api/test_app.py` **85 passed**。CI 因计费未启动，以上为本地实跑，不是 CI 绿。

## 2. 页面侧事实（给前端票 02 的实现者）

- 「修改尚未提交的部分」选项由**后端发布**在生日确认/验证交互上（`InteractionRequest.options`，label「修改尚未提交的部分」）；前端不得按文案匹配，只能消费后端给的 option id。
- 受控编辑成功返回**同 task_id、新 task_revision、新 interaction_id 的 waiting_input**，并已写入历史/SSE（事件 id 由 `edit_ref` 稳定派生，重放不重复）。
- 错误映射：`INTERACTION_STALE`/`TASK_CHANGED`/`PUBLISH_CONFLICT`/`TRANSITION_PENDING` → 409「刷新后重试」；`ACCESS_DENIED`→403；`TASK_NOT_FOUND`→404；`CROSS_*`/`AUDIT_UNAVAILABLE` → 503「原任务结果待核实，请查询原任务」；内部码不出现在错误体。
- 未做（需前端/后续票）：新 waiting_input 卡以外的**页面渲染、键盘/200% 缩放/读屏**；见走查脚本 D01—D11 与 N01—N10。

## 3. 明确未做/交接缺口

1. **页面已走查通过并实现**（2026-10-26）：本人 D01—D11 通过、批准 6 条补充文案；前端 02 已 PR #314 合入（`4d2201a`）。剩余为视觉/键盘/200%/读屏/真实 E2E 的实机验收（留本人）。
2. **真实 E2E 未跑**：设计沿 [v05-cross-e2e/03 生日 E2E](../../v05-cross-e2e/issues/03-birthday-e2e.md)；本次只做局部与真实组合测试（真实安全/银行/存储/平台装配），不是页面/模型 E2E。
3. **跨会话恢复**：G3 生日任务迁移会话前显式拒绝（不静默分叉），适配器接线留 04/08 后续；旧任务/legacy 编辑仍 `SOURCE_UNAVAILABLE`。
4. **普通输入发布断点**：平台已预留但发布 CAS 失败时，目前只由平台侧按原 request 恢复，API 未开放同 request 自动重试（api README 已记）。
5. **安全语义扩展待确认**：平台 09 把 `get_retirement` 的只读回查扩展为「同参新尝试」复用闸门（只读既有 sealed 事实、不改 security 代码）；v0.5 由 Erwin 代行记录，非 Ringo 本人签核。
6. **200%/读屏/真机、页面验收、最终安全与体验接受**：均留本人安排。
