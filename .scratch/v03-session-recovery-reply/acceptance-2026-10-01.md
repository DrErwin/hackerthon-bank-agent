# 补票 01—04 验收记录（2026-10-01）

结论：本次验收未通过，实施代码未合并。用户授权验收、通过后合并及更新文档；两个 P1 问题阻塞恢复链路。本次记录不将缺陷修复或真人批准记为已完成。

## 对象与证据

- 工作组：[v03-session-recovery-reply](spec.md)。
- 比较基线：`041a6e4`；本地集成分支：`codex/recovery-api-04`，提交 `e786e644737e82085e5f0bbf9905bf95bde8d34e`。
- 该提交尚未推送、无对应远端实施 PR。原实现工作树与分支保留。
- 在集成工作树的 `backend/` 运行 `python -m pytest -q`：204 passed，148.18 秒。
- 在仓库根运行 `python -m pytest -q evals/mockbank/test_mockbank_eval.py`：14 passed。
- `git diff --check origin/main...HEAD`、`python .github/scripts/check_links.py`、`python -m compileall -q tools backend .github/scripts` 均通过。
- Python 使用主工作树的 `backend/.venv/Scripts/python.exe`；测试工作目录为被审集成工作树，测试通过不能证明下述未覆盖场景通过。

## Standards：1 项 P1

**任务保存后、首个业务检查点建立前中断，新会话无法恢复。**

位置：集成提交的 `backend/app/agent_platform/harness.py:440` 与 `backend/app/modules/transfer/workflow.py:594`。Harness 总是调用业务恢复，但业务检查点不存在时返回 `TASK_NOT_FOUND`。

复现：使用 `app.agent_platform.test_transfer_runtime.runtime` 与临时数据库建立 S1；通过公开 `harness.start` 发起转账，在 `TransferWorkflow.start` 进入图执行前注入异常；此时任务及模型候选已持久化，业务检查点尚未建立。建立同用户同轮次的有效 S2，通过 `harness.recover_session` 连续恢复两次，均得到 `ValueError: TASK_NOT_FOUND`；任务已经转至 S2，标记保持 `transitioned`。未修改仓库代码。

违反票 03“中断后能恢复原转换”及安全底座原则的数据层恢复要求。修复方向：已有任务没有业务检查点时，使用原请求和已保存候选继续初始化，保留原任务及已预留操作，不能重新规划或重复扣款。需补重启回归。

## Spec：1 项 P1

**恢复中断后再次登录，覆盖了仍需使用的原会话信息。**

位置：集成提交的 `backend/app/agent_platform/harness.py:375` 与 `backend/app/modules/transfer/workflow.py:608`。

复现：临时数据库中以 S1 启动任务；建立 S2，在 `TransferWorkflow.recover_session` 迁移检查点前注入异常，Harness 已将应用任务归属改为 S2，业务检查点仍属于 S1。建立同用户同轮次的有效 S3，正常调用 `harness.recover_session` 连续两次，均得到 `ValueError: ACCESS_DENIED`。Harness 将 S2 当成业务源会话并覆盖原标记，因而无法继续 S1 检查点。未修改仓库代码。

违反票 02“覆盖服务重启、转换中断及重复恢复”与票 03“中断后能恢复原转换”。修复方向：保留未完成转换的原始检查点归属，让当前有效身份安全续做；同时验证检查点已迁移与尚未迁移的中断窗口，不借用过期会话授权。

## 各票状态与合并门槛

| 完整票号 | 本次结论 | 下一步 |
|---|---|---|
| [v03-session-recovery-reply/01：原任务的新会话归属转换](issues/01-task-session-transition.md) | 未发现独立代码阻塞，实施尚未合入 | 安全审查、单目录 PR |
| [v03-session-recovery-reply/02：转账公开新会话恢复](issues/02-transfer-session-recovery.md) | 未发现独立代码阻塞，整体恢复仍依赖协调修复 | 安全审查、单目录 PR |
| [v03-session-recovery-reply/03：Harness 新会话恢复协调](issues/03-harness-session-recovery.md) | 验收未通过，两个 P1 | 修复、增加回归、复验 |
| [v03-session-recovery-reply/04：API 新会话恢复接入](issues/04-api-session-recovery.md) | 现有 HTTP 测试通过，完整恢复验收受 03 阻塞 | 在修复后的真实链路复验 |

四票均不标记完成；01 / 02 的正式依赖仍需公开入口及合入证据。无重复扣款或权限绕过的已观察证据，但两个恢复死路足以阻塞验收。来源问题 #23 保持开放；05 / 06、真实模型、React、AF01—AF14 不在本次通过范围。

本地四票明确记录 Ringo 真人安全审查尚未完成。仓库 `docs/principles/03-review-and-merge.md` §5 要求“安全相关 ringo 未批不得合”；AI 审查不代表真人批准。已向用户请求批准记录或对本次门槛的明确决定，未收到回复前不将其视为已满足。
