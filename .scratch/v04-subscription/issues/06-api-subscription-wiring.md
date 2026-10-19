# v04-subscription/06-api-subscription-wiring: FastAPI 路由泛型放宽、F10 消歧输入与订阅模块接线

Ticket ID: `v04-subscription/06-api-subscription-wiring`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§5.6）
Core scenarios: SF01–SF05（F05/F06/F07/F08/F10 全链路）
Verification: 本票局部——`pytest backend/app/api/test_subscription_api.py -q`；整条路径由 `07-subscription-evals` 覆盖
Owner: Erwin
Directory: `backend/app/api/`
Status: resolved
Blocked by: [`01-contract-models`](01-contract-models.md)、[`02-mockbank-subscriptions`](02-mockbank-subscriptions.md)、[`03-subscription-module`](03-subscription-module.md)、[`04-security-policy-subscription`](04-security-policy-subscription.md)、[`05-platform-subscription-wiring`](05-platform-subscription-wiring.md)
Source issue: Issue #123

---

## 1. 目标（Why & What）

在 `backend/app/api/` 完成订阅模块的应用层组装，并把 v0.3 时代「只服务 `TransferTaskView`」的窄化注解与断言放宽，使 `F05 /chat`、`F06 /confirmations`、`F07 /verifications`、`F08 /tasks/{task_id}`、`F10 /tasks/{task_id}/inputs` 都能承载 `module="subscription"` 与 `SubscriptionTaskView`。

> **目录边界**：只允许修改 `backend/app/api/` 下的文件。平台行为由票 05 提供，本票只做 HTTP 层接线与分支。

---

## 2. 改动清单

### 2.1 `app.py`
- `/tasks/{task_id}/verifications`（及同类端点）的返回类型从窄化的 `VerificationResponse[TransferTaskView]` 放宽为兼容 `SubscriptionTaskView`（联合/泛型放宽），避免订阅任务验证完成后响应序列化校验失败。
- 确认/验证端点维持既有守卫（`record_ref`、`decision == "pending"`、原提交重试约束），仅把内部调用改为平台按模块分派的 hook。

### 2.2 `service.py`
1. **任务视图**：`task_view` / `_task_module` 支持 `module="subscription"`，`data` 按模块视图原样透出（不强行转成 `TransferTaskView`）。
2. **解除窄化断言**：`verification_fault` 等路径中 `ModuleResult[TransferTaskView]` 的强类型构造改为按任务模块构造（订阅任务用 `ModuleResult[SubscriptionTaskView]`），行为不变。
3. **F10 消歧输入**：`input_response` 在 `module == "subscription"` 且任务 `WAITING_INPUT` 时，接受 `selected_option_id`（如 `"sub_001"`）或 `text`（如「优酷视频」）；选项非法返回 `400 INVALID_OPTION`，与既有 transfer/bills 分支互不影响。
4. **订阅服务组装**：在运行时装配处注入订阅模块（票 05 的 `register_subscription`），登记 `module="subscription"` 的公开能力。

### 2.3 测试 `test_subscription_api.py`
HTTP 全链路（TestClient + 确定性测试双击）：
1. `POST /api/v1/chat` 「帮我看看有哪些自动扣费」→ `task.module == "subscription"`、`data.action == "list"`、`upcoming_renewals` 2 条、`upcoming_total_fen == 6400`、`active_count == 2`；
2. 「把优酷视频自动扣费退了」→ `waiting_approval` + `confirmation` 交互 → `POST /confirmations/{id}/answer` 确认 → `waiting_approval` + `verification`（`purpose="basic_identity"`、`scope="session"`）→ `POST /verifications/{id}/code` 提交 `123456` → `succeeded` 且 `data.operation.receipt.mandate_id == "sub_001"`、`status == "cancelled"`；
3. 同 `session_id` 续退「云端网盘」→ 确认后直接 `succeeded`（复用会话验证，无需再输码）；
4. 「把所有自动扣费都关了」→ `waiting_input` + 候选 2 项 → `POST /tasks/{task_id}/inputs` 传 `selected_option_id="sub_002"` → 进入 `waiting_approval`(confirmation)；
5. 「帮我把绿洲健身每个月扣的钱退订掉」→ `succeeded` 且不含确认交互、`data.selected_item.can_cancel_in_bank == False`；
6. 高危话术 → 任务终止且银行协议状态不变。

---

## 3. 验收与自检命令

```bash
pytest backend/app/api/test_subscription_api.py -q
pytest backend/app/api -q      # 不破坏既有 API 用例
```

---

## Comments

- 2026-10-19 开工（API 线，worktree 基于票 05 提交 `5a810b6`）：放宽 `/tasks/{task_id}/verifications` 等端点的窄化返回类型、按任务模块构造失败结果（`verification_fault`）、`input_response` 支持订阅 `WAITING_INPUT` 的 `selected_option_id`/`text` 消歧，并补 HTTP 全链路测试。
- 验收命令以目录为准：`pytest backend/app/api -q`（避免只跑单个文件出现假绿）。
- 2026-10-19 实施（API 线）：`app.py` 去掉 `VerificationResponse[TransferTaskView]` 窄化（按任务模块选泛型）、`service.py` 新增按模块的任务视图映射与 F10 订阅消歧（`selected_option_id` 原样透出、`merchant_hint` 文本映射、非法选项 400）、`verification_fault` 不再把订阅快照强套 `TransferTaskView`；新增 8 项 HTTP 全链路用例。
- 票据口径更正（实现与票据字面不符，属票据文字问题）：验证码用银行 F19 演示码（`GET /verifications/{id}/demo-code`），票据字面的 `123456` 不成立——银行只认自己按 `demo_secret` 签发的 6 位码，既有 transfer HTTP 用例同做法；F07 的 `VerificationView` 不含 `purpose`/`scope`，这两项在平台接缝断言（与票 05 运行时测试一致），若要 HTTP 响应直接带需契约层加字段另开票。
- 2026-10-19 联调阻塞：订阅任务出现约 1.9%/引用的随机失败，根因在 `audit/`（脱敏改写不透明引用），另立票 08（PR #153）修复；本票测试在修复后稳定全绿（`backend/app/api` 84 passed、`backend/app/api + audit` 95 passed）。
- 交付：**PR #154**。
