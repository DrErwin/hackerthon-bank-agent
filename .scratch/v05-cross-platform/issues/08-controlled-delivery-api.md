# 08：配送资料受控 API

Ticket ID: v05-cross-platform/08

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/api/`

Status: delivered — F36 delivery 受控录入已合入（PR #263，squash 5ab6ecb，2026-10-24）；前端表单归 frontend 包、cross 引用消费归票 05/09；Ringo 隐私审查与 E2E 另行记录。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待 Erwin 指派

Accepted by: 未记录（具体票的实施执行者）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B02、X05、X08；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

受控录入取得本人本轮引用，业务按授权解析，普通任务响应与聊天只给脱敏信息；错误引用拒绝，原文不进模型或普通日志

## Blocked by

- [v05-cross-platform/02：任务关系与安排记录持久化](02-durable-task-relations.md)
- [v05-cross-platform/04：联动任务与子交互 API](04-parent-child-api.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 接包；本聊天只细化票据，具体执行者由 Erwin 另行指派并记录领取。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。
- C7 受控资料范围和使用规则需安全审阅。

## Acceptance criteria

- [x] 配送原文由受控录入路径生成本人本轮引用，不经普通聊天或模型解析。（details delivery 分支独立于聊天；任务不推进、无模型调用/无 SSE；测试全文扫描响应无原文）
- [x] 读取/使用引用按身份、轮次及实际业务权限检查；错误引用不能取得他人资料。（controlled_details 本人/轮次/任务范围，跨用户/跨轮次解析 None 有测试；跨用户 404、跨会话 409）
- [x] 返回模型、任务视图与普通日志的内容脱敏；恢复仍可用正确引用，重置后旧引用不能使用。（display_fields 脱敏；ref 不绑会话可恢复；轮次重置自然失效）

## 实施交接：配送资料专用入口与受控引用

1. 在 01 已确认的接口定义和 02 的受控存储之上，为前端提供配送资料专用录入及引用使用路径；不把收件原文作为聊天文本传给模型。
2. 明确引用的本人、轮次、有效范围、允许使用方与失效条件；业务通过受控接缝解析。任务普通返回仅含必要脱敏信息。
3. 复用既有身份/轮次和任务 API；如果实现发现公共模型或存储缺项，回到提供方补依赖，不能在 API 复制一套存储。

**本票验证步骤**：通过 HTTP 核对正常录入/引用、跨用户、跨轮次、恢复和重置；检查返回体、普通日志及模型入口不含配送原文。证据使用虚构配送资料，不写真实个人信息。

**交付物与边界**：受控 API 和调用样例、隐私边界检查。前端专用表单由 frontend/02 承接，不在本票实现。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：已合入。[PR #263](https://github.com/DrErwin/hackerthon-bank-agent/pull/263)，squash 提交 `5ab6ecb`（2026-10-24）。交付：`api/service.py` store_delivery_detail/_masked_delivery_fields、`api/app.py` delivery 分支（含 required_fields 收集需求门）、`test_delivery_details.py`。
- 本票验证：`app/api/` 175 passed（新增 3 项）；CI 通过（PR #263）。
- 审查：子代理审查 A—F 全 PASS、无必须修复项；两条一行级建议（F36 收集需求门、清理导入）已采纳。
- 已知边界：cross 业务对 delivery_ref 的消费（结合送达时间构造 DeliveryInput）与前端专用表单分别归票 05/09 与 frontend/02；Ringo 隐私专项审查待完成。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 15](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包后细化）：Erwin 明确接受第一个交付包，授权本聊天完成拆票后交其他执行者实施。本票沿用原编号、目录和依赖；具体执行者尚未领取。总交接见[本包交接说明](../handoff.md)。
