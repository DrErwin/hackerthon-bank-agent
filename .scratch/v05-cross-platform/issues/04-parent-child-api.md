# 04：联动任务与子交互 API

Ticket ID: v05-cross-platform/04

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/api/`

Status: blocked — 包负责人已接包；实施仍待本票前置及 Erwin 指派执行者。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待 Erwin 指派

Accepted by: 未记录（具体票的实施执行者）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01、X02—X05；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

通用任务/交互/事件接口呈现父子真实状态；旧交互拒绝、重复提交不重复推进、取消与重登录恢复准确

## Blocked by

- [v05-cross-platform/03：Harness 受控子任务衔接](03-child-task-dispatch.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 接包；本聊天只细化票据，具体执行者由 Erwin 另行指派并记录领取。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] 任务查询和 SSE 返回真实父进度、步骤及当前子交互；不伪造结果或多建一份确认。
- [ ] 响应绑定子任务及交互版本；旧按钮、重复提交、越权和跨轮次拒绝且不产生额外业务写入。
- [ ] 父取消能停止后续动作，恢复能找到原子任务；HTTP 与事件视图含义一致。

## 实施交接：让页面操作准确落到当前业务

1. 使用 03 的真实任务机制，经既有查询、补充输入、确认、取消、恢复及 SSE 接口向页面暴露父总览与子交互。
2. 父卡片显示子交互，但提交时必须绑定动作真实所属的任务、交互及版本；不能复制一个另具效力的父级确认。
3. 新会话恢复、轮次重置和取消都按后端规则处理，REST/SSE 状态一致；不增加私有 cross 恢复 API。

**本票验证步骤**：通过真实 HTTP 测试客户端驱动父/子任务：旧交互和重复提交、错误用户、跨轮次、刷新重读、重登录及取消。核对返回 allowed_actions、实际推进次数和事件载荷；这仍是 API 局部验证。

**交付物与边界**：API 适配、响应/事件样例与 HTTP 测试。前端代码不在本票；配送录入单独留 08。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：未开始。
- 本票验证：未运行。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 4](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包后细化）：Erwin 明确接受第一个交付包，授权本聊天完成拆票后交其他执行者实施。本票沿用原编号、目录和依赖；具体执行者尚未领取。总交接见[本包交接说明](../handoff.md)。
