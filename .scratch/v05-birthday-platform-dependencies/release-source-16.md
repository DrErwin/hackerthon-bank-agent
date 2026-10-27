# 16：限定释放审计使用原批准来源

用户已要求完成非比赛资料任务；root 顺序领取本票，实施只在 `backend/app/agent_platform/`。依赖 [17：只读原确认](issues/17-release-confirmation-origin.md)，属于既有生日平台接线。

生日在 S1 冻结后，S2 的结束仍应按原批准条款释放未消费余额。释放本身没有新的确认；平台应在真实 S2 上下文调用安全公开 `get_release_confirmation(context, release_authorization_id)`，将原确认精确 ID/version 写入审计。不得伪装 S1，不用最新确认代替，不放宽普通 get/history，不新增付款或退款。

来源缺失、拒绝或无效继续通过原审计门暂停，不能把无来源写成批准。局部用真实 Harness/安全/MockBank 验证跨会话结束、历史原版本、重复收尾不重复写、缺失历史不释放；不使用真实模型。Cross09 的完整消费和六阶段成功另作组合验证，不将本票局部通过写成页面或真人安全接受。
