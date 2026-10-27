# 票10：G3 会话恢复 provider 验证

日期：2026-10-27；PR [#323](https://github.com/DrErwin/hackerthon-bank-agent/pull/323)。本票仅修改 `backend/app/agent_platform/` 与本组规格/证据。

## 实际验证

- 原入口对普通 G3 任务跨会话恢复返回 `DEPENDENCY_UNAVAILABLE`；新增真实组合回归先复现该缺口。已接入精确源、缓冲、封存与严格发布接缝。
- 中间回归发现同一恢复 marker 重复写入会令原受理版本失效，表现为 `PUBLISH_CONFLICT`。已避免相同 marker 无谓写入，并在已封存候选存在时直接核对原绑定后发布其 winner，不再次运行 Cross。
- 最终命令（设置 `PYTHONPATH` 为本 worktree 的 `backend`，解释器复用本机已装依赖）：

```text
python -m pytest backend/app/agent_platform -q --basetemp=<本worktree外独立临时目录> --junitxml=.scratch/v05-birthday-platform-dependencies/evidence/2026-10-27-platform10.xml
```

实际结果：**387 passed / 13 skipped，272.49 秒，exit 0**。13 skip 为已有端点测试；未将 skip 计作通过。

- [原始 JUnit](evidence/2026-10-27-platform10.xml)。受测 `agent_platform` 树为 `fddb59af18ce2392d481cec86426a447c8887398`；受测代码先提交 `11808cbd`，同步最新纯文档 main 后为 `ee50b117`，该目录树完全相同。
- `git diff --check` 通过。新增 11 个参数化实际节点覆盖普通输入恢复、故障消费方旧确认/验证卡拒绝、跨主体/轮次拒绝、原输入 pending/完成投影查询、后继输入后原投影不变、封存后发布断点、发布后完成断点、已完成恢复不得回滚后继输入及其他在途转换拒绝。

## API11 接缝

`BirthdayHandoff.find_input_conversion(trusted, request_id: UUID)` 只读返回：

- `PublicationOutcome`：原完成投影的 `result/task_revision/published_ref/content_digest/kind`；后继输入不改写该投影。
- `"pending"`：原 request 的 normal input 转换已受理但未发布。
- `None`：没有该原 request 的受理/完成记录。

该查询不替 API 校验原请求正文，不使任意旧 request 获得续做权。API 必须匹配原摘要；回复原回执时，不应把旧 winner 再发布为当前活动卡。

## 保留边界

- 规划器为明示替身，其余 Harness、Cross、存储、安全与模拟银行为真实本地组合；两个拒绝旧卡用例显式注入错误的 Cross 恢复返回。不是新真实模型、HTTP/页面 E2E 或真人签核。
- Cross 当前敏感等待会回缓存卡；本 provider 校验新会话的确认/验证记录，拒绝旧卡且不发布。该消费方 SOP 修正是后继 Cross 单目录票，不能把 provider 通过写成生日所有阶段恢复已验收。
- legacy 无 G3 的原恢复保持；无不可变来源的旧任务编辑仍明确拒绝。未改风险政策、公共契约、API、银行规则或共享演示库。
- AI 两轴审查由中控安排；远端 CI 依实际 head 单列，账号计费阻塞不写作通过。
