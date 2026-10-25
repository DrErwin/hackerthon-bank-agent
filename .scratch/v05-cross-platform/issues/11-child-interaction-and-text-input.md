# 11：子任务交互登记与联动文本输入

Ticket ID: v05-cross-platform/11

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（v0.5 本阶段统一负责）

Directory: `backend/app/api/`

Status: in_progress — 2026-10-25 执行对话接手实施；先写复现用例再改 `backend/app/api/`。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: Erwin 转交的执行对话（DeepSeek Agent，2026-10-25 接手，代行实施）

Accepted by: 未记录（执行对话已接手，待 Erwin 验收后记录）

Accepted at: 未记录

Planning approved by: PM，2026-10-25 页面走查裁定「批准另开平台微票，优先修 G1＋G2」。

Core scenarios: XL-S01、XL-P01、XL-B02、XL-B05；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

让联动派发出的子任务能用通用任务接口完成「确认 / 验证」，并让联动父任务能接收用户输入的金额、日期、配送引用编号。

## 背景（代码核对，见 `page-plan-01.md` §10 与 [backend-api-surface.md](../../v05-cross-frontend/research/backend-api-surface.md) §5 G1/G2）

- **G1**：联动父任务派发出的子任务（退订、转账）在等待确认或验证时，页面拿到子任务 `interaction.record_ref`，但此时调 `GET /api/v1/confirmations/{id}`、`POST .../answer`、`GET /api/v1/verifications/{id}`、`POST .../code` 会先在 `record_context()` 里查 `api_records`，查不到即 404；而 `child_tasks()` 只往 `api_tasks` 登记子任务，没有登记交互记录。
- **G2**：`POST /api/v1/tasks/{id}/inputs` 的 `input_response()` 只识别订阅、选项、`amount_fen`、`payee_hint`、`payer_account_id`；联动父任务的 `required_fields` 恒为 `["cross_selection"]`，带 `text` 的回答一律 400 `USE_CURRENT_INPUT_FIELDS`，而 `modules/cross` 本身支持文本（`PensionFlow.apply_text` / `BirthdayFlow.apply_text`）。

两处都是 API 层缺分支，不改契约字段、不改业务模块语义。

## Start when

- 前置票 [04：联动任务与子交互 API](04-parent-child-api.md) 已合入（#259）。
- 实施前先实机复核 G1/G2 是否真如代码所读（若已不存在，先回填结论再决定是否继续）。

## Acceptance criteria

原有三条验收条件原样保留；括号内只写**本票实际达成的子集与证据**，不由实施者改写验收口径：

- [ ] 联动子任务等待确认时：`GET /confirmations/{record_ref}` 能取到确认单，`POST .../answer` 能推进该子任务；等待验证时同理（含 `demo-code`、`resend-code`、`face/start` 按现有实现）。
  - 本票达成子集：记录绑定已证明（`record_context()` 解析到子任务；`GET /confirmations/{id}` 由 404 变 409，说明已进入安全服务而非记录缺失）。**完整的确认单读取与作答往返未在本票验证**，需要真实安全服务记录，交真实页面与 [E2E 包 05](../../v05-cross-linkage/packages/05-cross-e2e.md) 承接。
- [x] 登记是幂等的：重复读取子任务不会重复插入记录，也不改写已存在的记录归属。
  - 证据：`test_child_confirmation_and_verification_records_reach_the_generic_endpoints`（重复读 children 后 `api_records` 仍仅一行）。实现为 `INSERT OR IGNORE`（先写者胜）；记录 id 不透明且安全层仍复核 user/session/round/task，冲突不会把一条记录交给另一任务。
- [x] 联动父任务收到文本回答时，把文本原样交给模块（`{"text": ...}`），由模块自己校验；非法文本由模块返回的既有错误码呈现，不在 API 层编造业务规则。
  - 证据：`test_cross_parent_text_answer_reaches_the_module`（模块收到 `{"text": "1500"}`）。"非法文本"实际表现为模块重问并签发新 `interaction_id`（旧交互转 `INTERACTION_STALE`），不是 400。
- [x] 选项回答（`selected_option_id`）保持现有行为不变；非选项、非文本的空回答仍按现有错误返回。
  - 证据：`test_cross_parent_option_answer_keeps_the_choice_contract`（文本+选项 → 400 `INVALID_OPTION`，且模块未被推进）；空回答由契约 `ProvideInputRequest` 校验拦下。
- [x] 越权/跨会话/跨轮次行为不变：记录仍只属于该用户与轮次，别的会话不能借 id 取用。
  - 证据：权限与会话路径未改；既有 `test_stale_interaction_wrong_owner_and_relogin_are_rejected` 通过。本票**未新增**针对该记录的跨用户取用用例（安全层既有校验覆盖），不写成已测。
- [x] 回归：`backend/app/api` 全绿；后端全量 `1587 passed`、mockbank `14 passed`（PR 回填批次为准）。

## Verification

按可观察外部行为验证，报告输入、期望、实际与证据位置（测试名 + 关键断言）：

| 检查 | 预期可观察结果 | 本票状态 |
|---|---|---|
| 子任务确认可读可答 | 读得到 `display_fields`；答完子任务继续推进，父任务步骤状态随之更新 | **部分**：绑定接通、路由 404→409 已证；读取 `display_fields` 与作答推进未验证，交 E2E 包 05 |
| 子任务验证可读可交 | `GET /verifications/{id}` 返回挑战；`/code` 提交后按既有验证流程推进 | **部分**：验证记录绑定已由 `record_context` 断言；挑战读取与提交未验证，交 E2E 包 05 |
| 联动文本输入 | 父任务 `waiting_input` 下提交金额/日期文本，模块能收到并推进；非法文本返回模块错误 | **满足**：`{"text":"1500"}` 原样到达模块；带标签凭证仍 400 `USE_VERIFICATION_ENDPOINT` 且任务不动（`test_cross_text_answer_still_rejects_labelled_verification_codes`） |
| 幂等与隔离 | 重复读取不重复登记；其他用户/会话/轮次取用被拒 | **部分**：幂等满足；隔离沿用既有安全层校验，本票未加重测 |
| 既有回归 | 订阅/转账/账单用例全绿 | **满足**：后端全量 + mockbank（见 Delivery record） |

不把本票通过记成三主线 E2E 通过；真实页面验收归 [E2E 包 05](../../v05-cross-linkage/packages/05-cross-e2e.md)。

## Delivery record

- 实现 / PR：`backend/app/api/service.py`（两处）、`backend/app/api/README.md`（/children 与 F14—F17 前提）、`backend/app/api/test_parent_child_api.py`（新增 4 条用例）；PR #281。
- 本票验证：`app/api/test_parent_child_api.py` 7 passed；后端全量 `1587 passed`（12m19s）、`evals/mockbank/test_mockbank_eval.py` 14 passed（以 PR 最终提交批次为准）。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-25：页面走查发现 G1/G2 两处 P0，PM 当日裁定另开本票并优先实施。代码证据已在 `page-plan-01.md` §10 与 backend-api-surface.md §5 登记；本票不修改契约字段、不复制业务规则到 API 层。

2026-10-25（实施）：先写复现用例再改代码，两处现象均按原样复现：
- G1：子任务等待确认时 `record_context` 返回 404；在 `child_tasks()` 读取子任务后补登记交互记录（仅 `confirmation` / `verification` 两种），复现用例转绿（幂等，重复读取只一行；绑定后 `GET /confirmations/{id}` 由 404 变 409，说明已进入安全服务）。
- G2：实测拦截码不是 `USE_CURRENT_INPUT_FIELDS` 而是 `USE_VERIFICATION_ENDPOINT`——`safe_text()` 的裸码防护先把 `"1500"` 当作 4—8 位验证码拦下。修复在 `input_response()` 加 `cross` 分支：选项仍走原校验并回 `{"choice": …}`；文本作为模块控制值放行并原样转交 `{"text": …}`。

2026-10-25（独立审查后回修，AI 自审非真人）：
- **放行 / 仍拦截两栏**：`numeric_field=True` 只关闭裸 4—8 位数字的拦截；`probe_output` 的凭证识别、`password`/`otp` 等带标签形态仍拦。新增拒绝用例 `test_cross_text_answer_still_rejects_labelled_verification_codes`（`"验证码是 123456"` → 400 `USE_VERIFICATION_ENDPOINT`，模块未被推进、任务停在原交互）。
- **原文去向**：API 只存请求体 HMAC（`store.receipt`），cross 只存解析后的金额/日期/引用。**例外**：`pension.apply_text` 的 `basis` 阶段会把解析出的金额回显进提问文案（`pension.py:539-548`），该文案经 `service.message` 进入消息与 SSE；改前这类输入会被 400 拦住，属本票引入的可观测变化。已在此登记，**交安全审查判断是否收窄**（建议后续让 cross 在 `required_fields` 声明答案形态，API 复用现有 `amount_field` 判定，而不是整模块豁免裸码拦截）。
- **接口行为变化（前端须知道）**：文本回答后模块重问并签发新 `interaction_id`，旧交互提交变 `INTERACTION_STALE`（改前是 400 且交互不变）。
- **未做**：真实安全服务记录的确认/验证往返（测试替身造不出真实确认单），留真实页面与 E2E；跨用户取用该记录的新增用例未写（沿用安全层既有校验）。
