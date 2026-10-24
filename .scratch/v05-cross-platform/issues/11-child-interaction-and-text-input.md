# 11：子任务交互登记与联动文本输入

Ticket ID: v05-cross-platform/11

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（v0.5 本阶段统一负责）

Directory: `backend/app/api/`

Status: ready-for-agent — 2026-10-25 由 PM 走查批准新开；优先于前端票 01 实现。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待登记

Accepted by: 未记录（具体实施票）

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

- [ ] 联动子任务等待确认时：`GET /confirmations/{record_ref}` 能取到确认单，`POST .../answer` 能推进该子任务；等待验证时同理（含 `demo-code`、`resend-code`、`face/start` 按现有实现）。
- [ ] 登记是幂等的：重复读取子任务不会重复插入记录，也不改写已存在的记录归属。
- [ ] 联动父任务收到文本回答时，把文本原样交给模块（`{"text": ...}`），由模块自己校验；非法文本由模块返回的既有错误码呈现，不在 API 层编造业务规则。
- [ ] 选项回答（`selected_option_id`）保持现有行为不变；非选项、非文本的空回答仍按现有错误返回。
- [ ] 越权/跨会话/跨轮次行为不变：记录仍只属于该用户与轮次，别的会话不能借 id 取用。
- [ ] 回归：既有 platform 04 的子交互用例、订阅文本输入、转账补充输入不退化。

## Verification

按可观察外部行为验证，报告输入、期望、实际与证据位置（测试名 + 关键断言）：

| 检查 | 预期可观察结果 |
|---|---|
| 子任务确认可读可答 | 读得到 `display_fields`；答完子任务继续推进，父任务步骤状态随之更新 |
| 子任务验证可读可交 | `GET /verifications/{id}` 返回挑战；`/code` 提交后按既有验证流程推进 |
| 联动文本输入 | 父任务 `waiting_input` 下提交金额/日期文本，模块能收到并推进；非法文本返回模块错误 |
| 幂等与隔离 | 重复读取不重复登记；其他用户/会话/轮次取用被拒 |
| 既有回归 | 订阅/转账/账单用例全绿 |

不把本票通过记成三主线 E2E 通过；真实页面验收归 [E2E 包 05](../../v05-cross-linkage/packages/05-cross-e2e.md)。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-25：页面走查发现 G1/G2 两处 P0，PM 当日裁定另开本票并优先实施。代码证据已在 `page-plan-01.md` §10 与 backend-api-surface.md §5 登记；本票不修改契约字段、不复制业务规则到 API 层。
