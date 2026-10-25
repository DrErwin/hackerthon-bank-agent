# 01：预算 F10 来源持久化与受控恢复（建议）

Ticket ID: v05-budget-adoption-origin/01

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [预算采用来源最小设计](../spec.md)

Type: 开发建议，未授权实施

Owner: Erwin

Directory: `backend/app/agent_platform/`

Status: proposed_not_activated

Blocked by: 中控确认本组规格与最小票拆分；无需新增 storage 表或 #293 的 API 变更。

Core scenarios: O01—O08，定义见规格；预算业务语义仍由 cross06 实施。

## What to build

提供专用后台预算输入入口及当前调用来源读取。复用任务快照/CAS/锁，固定认证主体、原 F10 请求/交互/选项、原候选/计划绑定、写入前后任务版本；普通 resume 和模型不激活来源。来源记录不是采用或动钱授权。

## Acceptance criteria

- [ ] 先核对并持久来源，失败零模块调用；禁止模型字段创建来源。
- [ ] 核对当前等待输入、真实候选与原选项，记录 accepted_task_revision 与写后 dispatch_task_revision；不把 revision 当授权。
- [ ] 私有读取只对当前专用输入/受控恢复有效，跨任务/线程/异常返回不串用句柄，snapshot 中存在历史来源不等于当前可用。
- [ ] 同交互双请求、同号异参、旧候选和跨主体/会话/轮次均拒绝或仅返回原事实，不生成第二来源。
- [ ] 原来源 + 稳定 cross attempt 支撑断点恢复，result 与 completed 投影在同次 CAS 中保存；缺 attempt 不重新推定已采用。
- [ ] 首次/尚未采用的原写仍严格核对当前 input；已有采用事实的历史核实可处理 needs_attention / interaction=None，只补原结果，不激活来源/新写采用，取消/终态不继续新步骤。
- [ ] 修改/取消/新会话等不能复活旧来源；API receipt 断点恢复所需输出稳定可读。
- [ ] 提供 API 与 cross06 的调用样例，公共字段不变；设计若发现不能用现有持久接缝完成，先回中控，不跨目录写 storage。

## Verification

实施时用真实 Harness/ApplicationStore + 临时数据库验证 O02—O07；模块 stand-in 可验证平台边界，但不能代替真实 cross06 的 adopt 验收。API 尚未接线时用专用后台方法验证；真实 F10 联调由 02 与 cross06/原 E2E 完成。本轮未写运行代码或运行上述测试。
