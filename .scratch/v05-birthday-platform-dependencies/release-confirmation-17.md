# 17：限定释放原确认的只读来源

Status: developed — local checks passed; independent review/consumer integration pending
Owner: Erwin；Codex按中控本轮明确分派实施
Directory: `backend/app/security/`
Ticket: [v05-birthday-platform-dependencies/17](issues/17-release-confirmation-origin.md)
Source issue: [Issue #340](https://github.com/DrErwin/hackerthon-bank-agent/issues/340)

## 问题和范围

Cross09冻结已发生后，S2继续下单/核销的最终限定释放需要S1原冻结确认作审计来源。普通get/history正确按session拒绝S2，不能伪装S1、将旧批准转为新批准或放宽普通历史读取。原4 fail / 2 pass与既有授权/确认/操作/审计保留。

新增`SQLiteSecurityState.get_release_confirmation(context: ExecutionSecurityContext, release_authorization_id: str) -> ConfirmationRecord`：context是已认证当前执行上下文，其release_authorization_id必须与显式ID相同。只在同一只读SQLite快照中复用既有授权主体校验，按该授权精确绑定的confirmation_id/version读取当前或历史唯一原记录。

只接受active/completed且已绑定freeze_id的已生效记录，pending_freeze/invalid拒绝。原记录须匹配授权的user/session/task/round、freeze_operation、ID/version；action是bank.freeze_funds、approved且带原正式释放条款；action_revision有值必须一致，旧授权None时原精确ID/version仍唯一绑定原revision。不按当前时刻刷新旧确认或原session有效期；只核对原批准发生在有效确认期内且不晚于grant。

## 核心场景及验证

- RC17-1：真实冻结后跨S2只读取得原S1确认；原session/确认后来过期仍返回原已生效来源，不写expired、不撤销已生效权。
- RC17-2：S2复用同confirmation_id产生新version，原S1批准从精确历史读取；普通get/history仍严格会话，不取S2新确认替代。
- RC17-3：缺失、foreign user/task/round、不同上下文ID、invalid/pending、原ID/version/session/op/action/revision/approved clause异绑定拒绝。未找到唯一原记录或字段损坏不降级猜测。
- RC17-4：读取不覆盖当前S2、不grant/bind/claim、不退休/重绑、不改原审计/历史/事务；同一只读事务避免授权与来源跨快照拼接。迟到旧确认/授权回调不因读接口获得新能力。

先增加红例（接口尚缺），再最小实现；真实安全状态/确认/银行用临时新库，模型0调用。必要定向与安全目录回归后独立PR交两轴审查，平台16另票消费，不改Cross/平台生产，不代真人安全接受。

结果：[1 red / 47 targeted green / 574 security directory green](security17-verification.md)。仅提供方局部，消费及最终接受仍待。
