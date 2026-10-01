# 补票 01—05 验收记录（2026-10-01）

## 补票05本轮复验与修复

- 比较基线 `origin/main`（`2ecbe83`），PR #35 原提交 `ec1e7ef`；修复提交 `2f850b8`。
- Spec 复验发现两个 P1：模型回复的认证秘密先于脱敏写入持久检查点；英文 `password` 标签的秘密在回复及审计中未被脱敏。另有一个 P2：任务创建后、候选保存前中断，重试得到仅回复时原任务一直为 RUNNING，读取返回 TASK_NOT_READY。
- 三项均已修复：模型规划不配置持久检查点；回复在返回和写审计前复用现有凭据检查；已有任务重规划为仅回复时进入已有受控失败处理。银行与业务恢复仍走原任务检查点，不增加授权。
- 定向测试 **36 passed**；新增中英文模型秘密不落盘、初始化中断后受控失败用例。独立 Standards / Spec AI 复审无剩余阻塞；复现和测试均使用脚本模型，不代表真实提供商或 React 已验收。
- 本票仍等待真人安全批准或用户对此票的明确豁免，01—04的既有豁免不扩展至05。合入前05保持 in_progress、06保持 blocked，#24不关闭，v0.3不标完成。

初验未通过；用户随后明确要求修复、复验并合并。修复后双轴AI复审通过，实施已合入；最终主线验证和收口见文末。

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

## 初验各票状态与合并门槛

| 完整票号 | 本次结论 | 下一步 |
|---|---|---|
| [v03-session-recovery-reply/01：原任务的新会话归属转换](issues/01-task-session-transition.md) | 未发现独立代码阻塞，实施尚未合入 | 安全审查、单目录 PR |
| [v03-session-recovery-reply/02：转账公开新会话恢复](issues/02-transfer-session-recovery.md) | 未发现独立代码阻塞，整体恢复仍依赖协调修复 | 安全审查、单目录 PR |
| [v03-session-recovery-reply/03：Harness 新会话恢复协调](issues/03-harness-session-recovery.md) | 验收未通过，两个 P1 | 修复、增加回归、复验 |
| [v03-session-recovery-reply/04：API 新会话恢复接入](issues/04-api-session-recovery.md) | 现有 HTTP 测试通过，完整恢复验收受 03 阻塞 | 在修复后的真实链路复验 |

四票均不标记完成；01 / 02 的正式依赖仍需公开入口及合入证据。无重复扣款或权限绕过的已观察证据，但两个恢复死路足以阻塞验收。来源问题 #23 保持开放；05 / 06、真实模型、React、AF01—AF14 不在本次通过范围。

本地四票明确记录 Ringo 真人安全审查尚未完成。仓库 `docs/principles/03-review-and-merge.md` §5 要求“安全相关 ringo 未批不得合”；AI 审查不代表真人批准。已向用户请求批准记录或对本次门槛的明确决定，未收到回复前不将其视为已满足。

## 修复后复验

修复快照 `8c7a6bebce26afdcfffb8b3a195f026399b0bd36` 保留原四票实现，并补齐两个原 P1、中断初始化时的新 P1，以及终态重复恢复运行编号不一致的 P2。

- 转账新增只读公开 `checkpoint_context`：只返回同用户、同轮次、同任务的检查点身份，跨身份拒绝；不执行银行、不授予旧身份权限。
- Harness 根据实际检查点归属继续转换；调用前持久化检查点源会话。尚无业务检查点时沿原请求及已保存候选初始化；初始化中断时凭持久标记继续原图，终态恢复返回当前运行关联的原结果。
- 新增 4 项真实 Runtime 故障恢复、1 项公开读取隔离与 3 项 HTTP 测试。8 项定向验证通过；HTTP 证明重新确认、验证、服务重启、重复回执与最终单次扣款；终态重复恢复不重复提交。
- 最终全后端 212 passed（169.16 秒），模拟银行 14 passed，文档链接、语法及差异空白检查通过。Standards / Spec 最终 AI 复审均为 0 项 P0–P3，早期发现已修复。结论不代表 Ringo 真人安全批准。
- 用户第二次明确要求“修复，然后验收完合并”；实施合并仍须处理仓库记录的 Ringo 审查门槛。

修复复验后、用户明确豁免前，01—04工程验收通过，但真人安全审查门槛与实施合入未完成；[票 01 PR #30](https://github.com/DrErwin/hackerthon-bank-agent/pull/30) 已建立，其余按依赖与最多两个开放 PR 的约定推进。主线仍不包含本地集成修复；#23 未关闭。

## 用户豁免、合入与最终收口

用户于2026-10-01明确指示「我豁免批准，合并」，本轮补票01—04的Ringo真人批准门槛由用户豁免；AI复审不记为真人批准，长期审查规则不变。

[PR #30](https://github.com/DrErwin/hackerthon-bank-agent/pull/30)、[PR #31](https://github.com/DrErwin/hackerthon-bank-agent/pull/31)、[PR #32](https://github.com/DrErwin/hackerthon-bank-agent/pull/32)、[PR #33](https://github.com/DrErwin/hackerthon-bank-agent/pull/33)已按01 / 02→03→04顺序合入，四票目录边界与依赖闭合；具体合并提交见[v0.3完成情况](../../docs/versions/v0.3.0/completion.md)。[代码主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36774040361)通过：后端212项（63.64秒）、模拟银行14项（0.46秒），文档链接、Python语法及差异空白检查通过。四票标为resolved，#23已关闭；#24、真实模型、React与AF01—AF14仍待完成，未同步飞书。

## 补票05本地验收与待办（2026-10-01）

- 对象：[v03-session-recovery-reply/05：Harness 无业务意图仅回复](issues/05-harness-reply-only.md)，单目录 `backend/app/agent_platform/`；分支 `codex/v03-session-recovery-reply-05`，工作位于新 managed worktree。未修改主 checkout。
- 实现结果：`DeepAgentPlanner` 在转账候选与仅回复间要求恰好一个结果；`AgentHarness.understand()` 和 `handle_message()` 支持无业务任务的回复，保留显式转账及旧 `start()` 兼容。仅回复不创建任务、不调用银行 / 转账能力或生成授权；回复在返回前脱敏。模型缺失、矛盾和失败结果均安全停止。
- 审计隐私：含凭据输入在 trace / 模型调用前拒绝；受控输出保存为可读取的脱敏快照。当前 Harness 无法读取 Deep Agents 最终发出的系统提示与会话上下文，`model.started` 明确记录 `evidence_status=missing` 及原因，不以摘要冒充完整模型请求回放。
- 验证：agent_platform 定向 **33 passed**；后端全量 **225 passed**（157.05秒）；模拟银行评测 **14 passed**；文档链接检查与 `git diff --check` 通过。脚本模型用例不证明真实模型行为；React / 真实模型验证未完成。
- Standards / Spec 最终 AI 复核未发现剩余代码问题。隐私与审计改动仍须 Ringo 真人安全审查；01—04 的既有用户豁免仅限该轮补票，本票未获豁免。[PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35) 的 Repository checks 已通过。
- 05 保持 `in_progress`，合入前置条件未满足；[v03-session-recovery-reply/06：API 仅回复接入](issues/06-api-reply-only.md)继续 `blocked`。#24、原票 10 / 12 与 v0.3 收口保持未完成。

- 最终修复复验：后端 **228 passed**（120.43秒）、模拟银行 **14 passed**（1.05秒），文档链接、Python语法及差异空白检查通过；代码提交 `2f850b8` 的 [PR CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36807503540) 通过。


## 补票05合入记录（2026-10-01）

用户在已告知本票缺少Ringo真人批准后明确指示「补票05合并」，本轮依该指示批准合入，豁免仅限补票05；不记录为Ringo真人批准，长期审查规则不变。[PR #35](https://github.com/DrErwin/hackerthon-bank-agent/pull/35)已squash合入main，提交 `0613a1a1eb8df9bde86de1c0d364bee48f4664cc`；最终PR提交 `36713e4` 的CI通过。三个验收问题的修复均包含在合并提交中，定向36项、后端228项、模拟银行14项通过，双轴AI复审无剩余阻塞。[合并提交主线CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36810100834)通过：后端228项（70.51秒）、模拟银行14项（0.47秒），文档链接、Python语法及差异空白检查通过。05标为resolved。

05已合入；06的公开能力及合入前置依赖已提供。06的API实现及验收仍未合入，Issue #24保持开放；真实模型、React、原票10全部验收、原票12和v0.3联合收口均未完成，未同步飞书。此前待批准、未合入等条目为历史记录。

## 补票06：API 仅回复接入（2026-10-01）

- 前置补票05已由PR #35合入main（提交0613a1a）；ticket 06分支已按用户指示切到合并后的main基线54b6e7c8ef9f77a09d4ca4db41b66fea33e42fa8，仅保留backend/app/api目录实现及相关过程记录。
- API收到消息后先持久化用户消息与可恢复作业并返回202，任务编号暂为空；由公开Harness handle_message结果决定仅回复或关联转账任务，不在API做关键词分类。仅回复写入助手历史与稳定SSE事件，不创建API任务、确认、验证或银行调用；同请求回放原受理结果，异内容仍冲突。转账沿既有确认与执行流程。
- 验证：完整后端234 passed（168.83秒），API单目录41 passed（116.02秒）；MockBank评测14 passed；API三个源文件Pyright 0 errors；Python compileall、文档链接检查及差异空白检查通过。
- 真实模型、React、原票10全量验收、原票12和v0.3联合验收仍未完成；#24保持开放。补票05的用户豁免仅适用于05；未记录Ringo对06的真人安全批准。Standards / Spec双轴独立AI复审均无发现；AI复审不表示真人批准或阶段验收。Draft [PR #37](https://github.com/DrErwin/hackerthon-bank-agent/pull/37) 已以main为基线打开，head为a34661a；Repository checks已通过（[CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/36812809932)）。
