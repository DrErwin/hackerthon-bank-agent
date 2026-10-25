# v0.5 转账 D1 冲突呈现

Status: in_progress
Owner: Erwin
Accepted by: Erwin 授权执行对话
Accepted at: 2026-10-25

## Problem Statement

平台已经暂停与活动资金安排冲突的支出并保证银行零写入，但转账把 ARRANGEMENT_CONFLICT 渲染为普通安全暂停，错误来源、字段和原因不符合现行契约。
来源：[v05-cross-platform/03：受控子任务衔接](../v05-cross-platform/issues/03-child-task-dispatch.md) Delivery record。
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)。

## Solution

按现行公共契约第5.4节修订，将 D1 PAUSE 呈现为 code=ARRANGEMENT_CONFLICT、source=platform、field=payer_account_id，message/reason 使用平台已有说明。仍为 needs_attention、recovery_required，不新增执行或放行。

## User Stories

1. 用户能知道付款账户已有联动资金安排，应先完成或结束该安排。
2. 用户不会把安排冲突误读为银行拒绝或暂时无法安全核对。
3. 其他暂停、高风险拒绝、未知结果回查继续原有行为。

## Implementation Decisions

仅转账模块及本工作组材料。SecurityDecision 没有 source/field 字段，转账按已冻结 ARRANGEMENT_CONFLICT 错误码映射到契约指定来源与字段；不扩公共模型或修改平台/安全门。原 message 从真实决定保留，其他暂停文案不变。

## Testing Decisions

TA01：D1 PAUSE 的 code/source/field/message/reason/status/recovery/allowed_actions；TA02：真实 runtime + 隔离 SQLite/种子银行，沿原确认和验证得到真实冲突，并证明无 B09 提交/无银行流水/余额不变；TA03：其他安全暂停和 reused claim 文案不回归。公开 workflow + 真实 runtime 是既有验证接缝，不新增测试接口。后续页面联合验收复用联动 E2E 包；本票不声明页面、真实模型或专业安全验收。

## Out of Scope

不改变 D1 规则、继续策略或安排结束流程；不改安全、平台、API、前端、银行、共享项目跟踪和版本完成状态；不合并 PR。

## Further Notes

用户已确认本票范围、粒度和实施。沿用本轮已读 implement 流程；该本机文件未在当前会话注册可调用，不冒充已调用。code-review 使用规范、规格双轴子代理审查；PR 沿用 pr 模板。技能文件沿用团队基线 d81f3a183412e71a5b1e84ca21bc1a35eea03a60，无安装升级。
