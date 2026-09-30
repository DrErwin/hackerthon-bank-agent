# 10：实现任务 API、确认验证与事件流

Type: task\
Status: claimed\
Owner: Erwin\
Executor: Codex（按本任务授权执行 Erwin 工作线）\
Started at: 2026-09-30\
Directory: `backend/app/api/`\
Blocked by: 02、05、07、09\
Integration dependency: 04\
Unlocks: 前端真实联调、12

## 业务目的

给最小前端提供一组真实、稳定的服务入口，让用户能够发消息、补充信息、选择候选、确认、验证、取消、恢复并查看结果和只读时间线。

## 交付

- v0.3 需要的会话、消息、任务查询与恢复入口。
- 候选选择、任务补充、确认、验证和取消入口。
- SSE 事件流与断线重连所需的事件游标。
- 当前演示用户的服务端身份、会话和任务归属核对。
- 只读运行时间线和证据读取入口。
- FastAPI 应用启动与接口测试。

## 验收

- 前端不需要调用业务模块、模拟银行或安全目录的内部函数。
- 服务端对每次确认、验证、恢复和时间线查询重新核对用户与任务归属。
- 旧确认、重复点击和跨用户任务引用返回确定性错误，不产生资金动作。
- SSE 断线重连继续原事件序列，不创建新任务。
- 页面刷新后能根据原任务状态恢复正确界面。
- API 层只负责身份、协议和协调，不包含转账 SOP 或银行规则。

## Handoff

向前端负责人提供启动方式、接口地址和可用的演示任务；前端真实联调完成后共同进入 12。

## Comments

- 2026-09-30：在独立 worktree、`codex/10-api-task-stream` 分支实施。依赖票已合入；使用现有 spec 和票据。代码改动限于 `backend/app/api/`，过程记录按队员开工规范更新。
- 已实现任务、确认、验证、取消与恢复、持久事件流及只读审计入口。启动配置和前端入口见 [API 交接说明](../../../backend/app/api/README.md)。
- 验证：完整后端 178 项（API 29 项）、模拟银行评测 14 项通过；API 类型、语法、文档链接检查通过。两位 AI 规范 / 规格审查及修复复查完成，非真人批准。公共缺口跟踪 [#23](https://github.com/DrErwin/hackerthon-bank-agent/issues/23)、[#24](https://github.com/DrErwin/hackerthon-bank-agent/issues/24)。
- 交付：[API 工程增量 PR #25](https://github.com/DrErwin/hackerthon-bank-agent/pull/25)；独立工程、契约与安全 AI 审查按本任务授权执行，已于 2026-09-30 squash 合入，提交 cd50ebdf36795b6883641e7494e4a29acfbbdcbc；[合并提交主线 CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36687051464) 后端 178 项、模拟银行 14 项通过，合并后跨会话回归 1 项通过。
- 本票保持 claimed（验收未完成）：公共 Harness 尚不支持新登录会话重新确认后恢复旧任务，也没有无业务意图时仅回复的结果类型；部署模型与策略组合工厂、React 联调及 AF01—AF14 联合验收仍待提供 / 执行。本次按用户授权由独立 AI 代相关角色审查并完成有限增量合入，未记录任何真人批准。AI 审查、工程测试和 CI 不代表这些条件已满足。

- 独立契约审查修复：新登录后的旧任务不再显示不可用操作，非终态明确标记 SESSION_RECONFIRMATION_REQUIRED；快照及待恢复列表有回归断言。工程增量获审查认可，票 10 全部验收仍未完成。
