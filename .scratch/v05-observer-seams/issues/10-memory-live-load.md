# 10 记忆真实载入会话：真实模型提示证据与复现脚本

Ticket ID: v05-observer-seams/10
Package: 无独立交付包——v0.5 平台遗留收口（[spec](../spec.md)），来源 [Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)
Spec: [v05-observer-seams/spec.md](../spec.md)
Core scenarios: S6（记忆载入会话 + F37/F38）
Type: 评测
Owner: Erwin（AI 代行实施与审查，非真人审查）
Directory: `evals/observer-seams/`
Status: Done
Blocked by: [v05-observer-seams/05](05-api-memory-endpoints.md)（F37/F38 已合入）、[v05-observer-seams/06](06-demo-slice-evidence.md)（评测目录已建立）
Source issue: Issue #216

## 背景

Issue #216 第 3 项要求「把受控记忆真实载入会话（当前只有离线断言）」。F37/F38 已交付（查看/删除），记忆经 Deep Agents `MemoryMiddleware.modify_request` 注入 system prompt（不是只进状态）；但**还没有真实模型提示层的证据**。本票补这一项：用真实模型 + 真实 `MemoryAdapter` 预置记忆跑一轮，证明提示里确实带载入的记忆，且回复能复述受控词表内容。

## 交付物

1. `evals/observer-seams/live_memory_load.py`（`--live-glm --config --output [--archive-dir]`，默认零成本计划模式不读配置；显式字段校验同 `live_demo_slice.py`）：
   - 临时数据目录 + `ApplicationStore` + `MemoryAdapter(active_round="D1")` + `memory.seed_demo("U1","D1","2026-09")` + 建立会话（`create_session`，未过期）；
   - 包装真实 `ChatOpenAI` 的 `_generate` 录制**发给模型的 system prompt**（只记脱敏后的关键行/哈希，不落全量提示、不落密钥），再用 `DeepAgentPlanner.select(..., catalog=[transfer.start_transfer], memory=adapter, thread_id=...)` 走真实规划；
   - 一轮问题：「请复述你记得的我的收入分配偏好和称呼线索。」；
   - 断言：①提示包含预置记忆内容（如「60% 转 A5 储蓄」/「妈妈 → 银行种子 A2」）；②请求里没有任何密钥/验证码；③回复（人工复核口径）复述出 60/20/20 或「妈妈→A2」至少一项；④真实调用计数如实记录、失败不重试凑绿；
   - 报告 schema `observer-seams-live-memory-v1`，写仓库外新路径；`--archive-dir evals/security/evidence/2026-10-22` 归档 gzip（`filename=""`、`mtime=0`）+ 追加 `evals/security/run-log.md` 台账。
2. `README.md` 补这一轮的复现命令与判定口径（1 次真实调用，计入 #216 小批量预算）。

## 验收

| 编号 | 场景 | 通过条件 |
|---|---|---|
| J01 | 提示含记忆 | 真实模型调用前的 system prompt 中出现预置记忆行（记录命中项与哈希，不落全量提示） |
| J02 | 回复复述 | 真实模型回复复述出预算比例或称呼线索至少一项（脚本记关键词命中供人工复核，**AI 代行初判、非真人签核**） |
| J03 | 无泄密 | 提示与报告不含任何密钥、验证码、完整账号；报告只写模型/端点摘要 |
| J04 | 真实调用计数 | `real_model_calls` 恰好 1（不含失败重试；失败如实记 Blocked/Failed） |

## 备注

- 真实调用由 Lead 执行（PM 已批预算；本票 1 次，总批次不超过 6 次）。
- 不改 `backend/`；只新增 `evals/observer-seams/live_memory_load.py` 与 README 一段。

## Comments

- **2026-10-22 交付**：[PR #226](https://github.com/DrErwin/hackerthon-bank-agent/pull/226) squash `7932eb4` 已合入。真实模型批次（Lead 执行，GLM-5.3 @ Coding Plan，1 次调用）：**4 Passed / 0 Failed / 0 Blocked**。J01 捕获到 system prompt 含预置记忆行（`称呼线索：妈妈 → 银行种子 A2`、`收入分配偏好：60% 转 A5 储蓄…`，只记关键行与 SHA256，不落全量提示）；J02 回复复述 60/20/20 与妈妈→A2（AI 代行初判，非真人签核）；J03 无密钥/验证码/完整账号；J04 真实调用 1 次。证据归档 [live-2026-10-22-observer-seams-memory-load.json.gz](../../../evals/security/evidence/2026-10-22/live-2026-10-22-observer-seams-memory-load.json.gz)（gzip `e12ddeb13249455a…`、解压 `d5d083b55061b193…`），run-log 已登记。
