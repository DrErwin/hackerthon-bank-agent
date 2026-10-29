# 普通聊天继续原任务：API消费

Status: in_progress
Owner: Erwin（v0.5）；执行 transfer_pause_recovery AI 子代理
Accepted at: 2026-10-29
Package: [v05-cross-linkage/packages/01-platform-bank](../v05-cross-linkage/packages/01-platform-bank.md)
Provider: [01：平台无字段继续建议](issues/01-provider.md)，明确依赖生产源c8d476efd5c8511f85afc02dd4191bc09b09feb2

## 问题与目标

减支父任务仍running且允许resume/cancel，视频子任务已经成功，普通聊天“继续”却没有推进。平台缺少resume建议的提供方由另一张票处理；API现有缺省分流会把新增resume误作query。本票只消费既有批准合同，不复制提供方实现。

## 最小合同

只消费无额外字段的ContinueProposal(action=resume)。API重新核当前身份、原线程、原task/revision、recovery和allowed；明确resume分支还核running且无interaction，映射为现有continue_task的 `{"choice":"resume"}`，publish=False，不设置recover_session。公开F11虽然使用同一choice，但其会话恢复授权不能借给聊天。

空response由Cross视为advance；显式choice=resume由Cross再次核当前resume可用性。API选择后一既有语义，不自行选菜单、批准、验证、查询新操作或补业务参数。query保持query:true；确认/验证码仍使用专用入口。

## 场景与验证

| 编号 | 验收 |
|---|---|
| C201 | 真实Cross/Harness/HTTP/模拟银行完成视频退订后，普通聊天继续同一父任务，进入真实后续选择而非query错误 |
| C202 | 同chat job原request UUID重复，回原receipt，不重复模型理解、推进父任务或银行写 |
| C203 | 已推进但API内部receipt写入中断，原请求重放只读取当前原任务，不再推进 |
| C204 | 当前无resume、恢复未决、输入/确认/验证交互、未知资金不因聊天继续而执行 |
| C205 | 当前版本、线程、会话或身份变化仍拒绝，不能把F11恢复权限带入聊天 |

先在明确provider依赖、API尚未修改的固定源捕捉真正consumer红例，不能把旧schema拒绝当API红。只做必要API/聊天续办与相关子任务回归，不重跑全量或真实模型。测试规划输出为替身；真实页面仍由根操作复验。

## 边界与执行

仅backend/app/api/和本票consumer文档/证据。原消息job receipt、专用验证中断恢复、身份与安全门不变，不修改公共字段、平台、Cross、安全、前端或共享演示库。新分支复用干净既有managed worktree；依赖在Git祖先中明确叠加，不把提供方文件放进本票差异。

根已明确单票粒度、接缝和继续修补授权；已读取to-spec/to-tickets/implement/pr/code-review流程，禁用自动调用的技能不冒称工具调用。作者交回PR，根安排独立两轴、精确head CI、依赖合入顺序及原页面复验。
