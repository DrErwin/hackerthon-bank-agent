# 01：已采用个人预算持久化与改版

Ticket ID: v05-adopted-budget-storage/01

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [已采用个人预算持久记录](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/storage/`

Status: delivered — PR #293 草稿，本地全量与独立双轴 AI 审查完成，交中控排队；CI 账号账务受阻，不代表合入或真人安全签核。

Accepted by: Erwin（中控委派本执行对话）

Accepted at: 2026-10-25

Blocked by: None（公共模型及既有占用接口已在 main）

## What to build

落实现行 AdoptedBudget：受控持久采用、active/superseded 连续改版、来源任务与交互身份、准确引用和隔离候选读取、重开恢复。保留现有预算占用接口；业务匹配和额度判断留给 cross。

## Acceptance criteria

- [x] S01：真实落库、默认只列 active、准确引用/含历史读取、重开恢复。
- [x] S02：改版原子替换、明确旧版本、旧占用不丢；重复/跳号/过期改版拒绝。
- [x] S03：交互重放幂等、异参冲突、旧请求重放不激活 superseded。
- [x] S04：可信 user/round 与来源任务核对、任务版本守卫、跨主体/轮次拒绝。
- [x] S05：独立连接并发采用/改版，只产生一个新版本，无半更新。
- [x] S06：v5 迁移保留旧数据、初始化幂等、新轮次隔离。
- [x] 记录局部/全量实际验证、双轴独立审查、cross 调用样例与边界。
- [x] 创建并附加代码 PR，交中控排队；不合并、不改共享状态、不代签真人。

## Comments

2026-10-25：中控明确授权按本独立组单票推进规格、实施及审查。与原生日业务票的顺序依赖由中控维护，本票仅更新自己的记录。

2026-10-25：代码 [PR #293](https://github.com/DrErwin/hackerthon-bank-agent/pull/293) 已创建为草稿并附加本对话；[双轴审查](../review.md) Standards 0 必修、Spec 0 必修；[cross 接口调用与后续责任](../handoff.md)。实现 e43cc51、审查及交接 d0ae73e。

远端首轮 [run 40168903440](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40168903440) / check 121095548823（head d0ae73e）未启动任务，GitHub annotation 为账号付款失败或支出额度不足；CI=Blocked（账号账务），不是测试失败或绿灯。不改 workflow，不将本地结果代作 CI 通过。

## Validation（2026-10-25）

- 本票真实 SQLite 接缝 `python -m pytest -q app/storage/test_adopted_budgets.py`：最终 19 passed。覆盖 S01—S06。
- 存储回归 `python -m pytest -q app/storage/`：首轮 56 passed（本票当时 18 项）；随后增加的 previous_version=0 边界已随本票 19 项复验，最终也包含于下述全量。
- 独立隔离环境，从 backend 运行 `../.scratch/v05-adopted-budget-storage/__pycache__/runtime/Scripts/python.exe -m pytest -q -n 4`：**1607 passed in 361.16s**。项目锁定依赖按 pyproject 安装；仅隔离环境额外安装 pytest-xdist 3.8.0，未改项目依赖。最初系统 Python 全量因缺 langchain_openai 收集失败，隔离环境已解决；隔离环境串行全量因较慢主动停止，以本次完整并行结果为准。
- 同隔离环境 `python -m pytest -q ../evals/mockbank/test_mockbank_eval.py`：**14 passed**。
- `python .github/scripts/check_links.py`、`git diff --check`、`python -m compileall -q tools backend .github/scripts`：通过。
- [独立审查](../review.md)：Standards 必修 0 / 可选 0；Spec 必修 0 / 可选 1（故障注入探针纳入永久测试）。探针本轮已由审查者独立运行，无阻断项。
- 使用临时 SQLite 数据库和测试种子；未访问共享运行数据库、未调用真实模型、未做真实银行写入；没有以这些单层结果冒充 cross 生日预算 E2E、HTTP/React 或真人安全验收。

## Delivery

worktree：`v05-adopted-budget-storage/hackerthon-bank-agent`（独立 managed worktree，已附加本对话）。分支：`codex/v05-adopted-budget-storage`。PR：[#293](https://github.com/DrErwin/hackerthon-bank-agent/pull/293)，保持 draft 等中控处理 CI 外部阻塞与合入。cross 调用样例见[handoff](../handoff.md)，本存储范围无新增待裁定业务语义。共享项目跟踪、completion、包状态均未修改。
