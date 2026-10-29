# 生日敏感动作的跨会话安全撤离

Status: merged — PR #330 已合入 `d14677e6`；后续 Cross09 消费已合入，完整接受另记。2026-10-29 核对，最新结果见[v0.5 完成情况](../../docs/versions/v0.5.0/completion.md)。

原规格状态（历史）：implemented — independent review/consumer integration pending
Owner: Erwin；Codex 按本轮中控分派实施
Directory: `backend/app/security/`
Package: [v05-cross-linkage/packages/02-security：联动安全](../v05-cross-linkage/packages/02-security.md)

## 问题与目标

Cross09 真实组合探针（commit `4af3d4b06f01cfe085d9a8a45dd94893f0a6bce2`，原文件 `.scratch/v05-cross-business/session-recovery-09.md`）保留1 failed/1 passed：只刷新新会话卡片会重用原freeze operation，旧pending_freeze授权仍绑定旧session/确认版本，新grant正确冲突。原失败不改写。

本票沿已批准G2胜序：可靠证明未提交后撤离原attempt，旧挑战退役、旧pending授权失效且保留历史/审计，再由平台创建新attempt并重新确认/验证。不会将旧批准重绑新会话，不删除唯一或身份检查，不把未知当未提交。

## 核心场景

- SS01：目标会话持可信同user/task/round，源确认按旧ID/version从安全当前或历史记录读取；action/原operation/revision/参数引用精确匹配。
- SS02：begin与seal都在同一应用事务connection内调用平台validator，核对目标任务归属、原attempt仍为冻结发布/CAS来源与受控参数快照。False、异常、非bool拒绝。
- SS03：只有无claim且银行已退役原attempt挑战时才封存；任意processing/completed/unknown claim先胜拒绝，active真实冻结不能当未提交处理。
- SS04：封存与原pending授权invalid(RETIRED_UNSUBMITTED)、原绑定/源目标会话审计同事务；审计失败回滚并允许原号续做。
- SS05：同一目标会话同参重放幂等；异参、异user/task/round/session拒绝；普通G2入口不能绕过跨会话validator。
- SS06：迟到旧确认、验证码/人脸、grant/bind、执行claim不能复活；旧历史不改写，新attempt必须有新确认及新挑战。

## 接口与proof责任

`SQLiteSecurityState.begin_session_retirement(context, action, now, *, source_session_id, source_confirmation_id, source_confirmation_version, recovery_validator) -> RetirementRecord`。

`SQLiteSecurityState.seal_session_retirement(context, retirement_id, bank_evidence, now, *, audit_writer, recovery_validator) -> RetirementRecord`。

context是已认证目标session及原operation/revision；confirmation字段为None。validator签名为`Callable[[sqlite3.Connection, ExecutionSecurityContext, dict[str, object]], bool]`：dict由安全核实后提供原绑定和源/目标会话、operation/revision/user/task/round；平台必须用传入connection验证原发布事实/CAS与参数快照，不能仅复用另连数据库的_task_terminated布尔函数。

银行proof只能由真实gateway.retire_action_challenges原号返回，不能从请求/模型传入；平台冻结源绑定须在任何新check/新卡前完成。安全不复制银行挑战规则。平台负责sealed之后新attempt的唯一关联与发布CAS，Cross负责消费新卡；均另票。

## 验证与边界

按SS01–SS06在隔离应用/银行库验证真实安全状态、确认历史、银行退役与副作用；先红后绿，最后安全目录及受影响provider定向回归。真实模型、页面和最终本人安全接受单列；不运行96分类，不涉及比赛材料，不自合入或关闭#160。

本轮已按开工流程读取现有G2、安全原则及Skill文件；复用已定票粒度与接缝，不声称自动调用设置disable-model-invocation的slash Skill。中控与platform_completion已对齐同事务validator，授权直接实施。
