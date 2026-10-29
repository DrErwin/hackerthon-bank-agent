# F30—F32 演示整体重置协调

Status: merged — PR #329 已合入 `87e30a94`；整体重置与新轮再转账另有实际接口批，完整页面验收另记。2026-10-29 核对，最新结果见[v0.5 完成情况](../../docs/versions/v0.5.0/completion.md)。

原规格状态（历史）：implemented_pending_review
Owner: Erwin（v0.5）；执行：API 重置子代理
Accepted by: Erwin，通过 2026-10-27 全部非比赛资料任务授权及主代理明确分派
Accepted at: 2026-10-27
Package: [公共平台与银行](../v05-cross-linkage/packages/01-platform-bank.md)

## 目标与已定方案

依据公共契约 §6.8 F30—F32、§7.3：管理预览不重置，二次确认绑定当前轮次与管理员。确认后停止新业务，等待真正执行中的 API 工作及所有银行 future（包括生日和限定释放），再按同一管理号依次恢复银行、应用有效轮次、记忆预置和逻辑起点。全部完成前不发布新外部轮次或成功。

管理操作、确认消费与阶段持久化；失败或进程中断后按原号查询并以原 F31 请求续做。银行已成功时先查原银行管理结果，不再次清新业务。历史任务与审计保留，旧轮会话、按钮与可信执行上下文失效；不以删除共享数据库实现重置。F32 只读，不偷偷启动重置。

## 公开依赖

- PR #322 银行管理入口：`runtime.bank.reset_demo`、`get_demo_management_operation`、`current_demo_round_id`。
- services 后续票：`runtime.gateway.wait_for_inflight(timeout: float) -> bool`，超时 future 仍追踪且不关闭线程池。
- 平台后续票12：公开 `runtime.bank`、`runtime.set_demo_clock(at)`；风险策略、记忆和业务接缝使用银行持久可信轮次与共享时钟。旧 TrustedContext 直接调用也必须拒绝。
- 记忆沿用 `MemoryAdapter.reset_user(user_id, target_round_id, start_month)`，不修改 memory 或 storage。

## 核心检查

- M01：普通身份与错轮拒绝；预览重放不重复建确认，且银行零改动。
- M02：二次确认原号绑定、冲突拒绝；等待确认的业务不算银行执行在途。
- M03：在途时原号 running，不清银行且停止新业务；排空后同号续做。
- M04：成功后旧会话与旧任务不可操作，新会话进入新轮、记忆恢复预置；历史审计仍可查询。
- M05：银行或记忆故障保留阶段与管理号，部分完成不报成功；原请求恢复不重清新银行业务。
- M06：重新装配与旧启动配置不覆盖当前轮次、逻辑起点或原管理结果。
- M07：新管理员会话可只读本人持久重置记录所属的旧轮任务/事件审计；其他管理员、无管理依据的旧轮和普通用户仍拒绝，导出保持现行轮次归属。

## 验证与边界

最高接缝为真实 FastAPI / ApiService + 临时应用、银行、记忆数据库，使用固定规划器，不调用真实模型；上游尚未交付的公开排空/时钟接缝以明确测试装配提供，不冒称整体生产装配已验。分别记录 API HTTP、银行事实、记忆和原号恢复。只修改 API 及本组材料，不改前端、账号支付、共享库或比赛材料。已有 F10 恢复工作属主代理，避免修改其函数区域。

本机已读取 to-spec/to-tickets/implement/code-review；前三者标记 disable-model-invocation，按已明确批准范围形成规格与单目录实施票，不冒称调用 slash 工具。
