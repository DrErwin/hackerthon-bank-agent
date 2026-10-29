# 普通聊天继续原任务：底座建议接缝

Package: [v05-cross-linkage/packages/01-platform-bank：公共平台与银行](../v05-cross-linkage/packages/01-platform-bank.md)
Owner: Erwin（本执行代理代行平台目录）
Accepted by: 用户已授权完成非比赛资料任务，中控2026-10-29明确分派本次缺陷修复
Status: in_progress

## 问题与范围

真实减支父任务running、允许resume/cancel，视频子任务已成功后，普通聊天“继续”
得到拒绝。根保存51-reduction-continue-result.txt及cross-parent-snapshot.json，
原运行库不重放。17f平台ContinueProposal枚举没有resume；API缺省把其他动作作query，
后者另目录、另作者、另PR，本票只改agent_platform。

## 最小合同

`ContinueProposal(kind="continue_task", task_id, task_revision, action="resume")`。
text、selected_option_id及三个转账字段必须None或省略；空字符串不当无字段。
模型只建议，不能执行；task与revision来自系统摘要。既有唯一未完成任务、当前
user/session/round、revision、allowed_actions、权限与recovery门继续生效。
resume只接受running且无交互卡的当前任务，不能替代菜单、确认或验证。

消费者按原请求UUID调用既有continue_task，明确response={"choice":"resume"}，
publish=False，不映射query、不设recover_session。API仍核当前线程/身份/版本/
allowed，按其已有专用确认/验证码入口执行；本票不改API。

## 编号验收与已确认接缝

- R1：实际DeepAgentPlanner工具schema可记录一个无字段resume建议，Harness只返回
  原task/revision建议，不调用业务模块、银行写或改动原任务。
- R2：额外字段/菜单id、旧版本、多个任务、其他身份范围、无resume、终态与恢复
  未决，以及确认/验证/输入交互均拒绝；原query/cancel/revise不变。
- R3：模型提示区分“继续核实原进度”和授权。用户原话仍由模型理解，不加中文关键词
  直执行规则，不把普通聊天当确认/验证，不扩可执行权限。

测试接缝沿既有Harness.handle_message和真实planner工具绑定；固定模型为明确替身，
pytest全新临时数据，先红后绿。不调用真实模型、浏览器或运行中银行。API消费红绿
与真实页面回验由中控/消费者分别记录，不由本票局部结果冒称。

## 票与依赖

- [v05-cross-chat-resume/01：平台无字段继续建议](issues/01-provider.md)。
- API consumer由中控另派，依赖本票固定provider源码；不得把schema旧缺失当API红例。

## Skills与边界

已读to-spec、to-tickets、implement及tdd/pr要求。前三项本机标记
disable-model-invocation，按中控明确用户授权实施，不谎称已调用禁用skill。
只改agent_platform与本组scratch，不改公共冻结契约/安全/业务/API，不更新共享进度。
