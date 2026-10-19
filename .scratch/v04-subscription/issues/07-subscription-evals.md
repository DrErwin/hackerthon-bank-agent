# v04-subscription/07-subscription-evals: 订阅代扣黄金评测集与端到端回归

Ticket ID: `v04-subscription/07-subscription-evals`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§4、§5.7、§6）
Core scenarios: SF01–SF06 + 三条红线（确认门 / 口径边界 / 话术边界）
Verification: 整条路径验收——`pytest evals/subscription -q`，并产出可复跑证据到 `evals/subscription/evidence/<date>/`
Owner: Erwin
Directory: `evals/subscription/`
Status: resolved
Blocked by: `01`–`06`（全部前置票）
Source issue: Issue #123

---

## 1. 目标（Why & What）

在 `evals/subscription/` 建立场景 05 的黄金评测集与自动化回归，覆盖 PRD 验收例（T01/T04/T08/T09/T12/T13/T14）与 spec SF01–SF06，并对三条红线做机器断言：**确认门红线**（未确认不执行、逐笔）、**口径边界红线**（疑似不等于已证实、不可退项不调 B30）、**话术边界红线**（只承诺「从下一期起不再自动扣费，之前已扣的不退」）。

> **目录边界**：只允许在 `evals/subscription/` 下新建或修改文件。

---

## 2. 改动清单

### 2.1 黄金评测集 `golden_cases.json`
每条含：`case_id`、`scenario`（SF/T 编号）、`input`、`expected`（工具路由、状态序列、银行协议最终状态、必须出现/严禁出现的文案片段、确认与验证要求）。
1. `sub_eval_01_inventory_and_reminder`（SF01/T01/T14）：盘点返回 3 签约 + 1 疑似；`upcoming_renewals` 2 条、`upcoming_total_fen == 6400`、`active_count == 2`、优酷视频 `billed_count == 6`/`billed_total_fen == 15000`；回复含 7 天内扣款标注；已解约项不混入待退与疑似区。
2. `sub_eval_02_cancel_single_success`（SF02/T04）：状态经确认门与验证到成功；验证 `purpose="basic_identity"`、`scope="session"`、**非 `mock_face`**；确认与回执含「从下一期（…）起不再自动扣费，之前已经扣掉的钱不退」；**严禁**「会员可用至」「还能用到」「先退订再重新订阅」。
3. `sub_eval_03_session_verification_reuse`（SF03）：同会话第二笔仍过确认门、确认后直接成功、不再要求新验证码。
4. `sub_eval_04_suspected_ledger_guide`（SF04/T08）：不进确认门、不调 B30、`can_cancel_in_bank == False`、给出微信/支付宝/商户端引导。
5. `sub_eval_05_disambiguation_and_no_batch`（SF05/T12）：批量全退被拒并 `waiting_input` 单选；选择 `sub_001` 后进入确认门。
6. `sub_eval_06_idempotent_cancelled_and_high_risk`（SF06/T13/T09）：6a 已退项幂等告知；6b 确认前取消 → `cancelled` 且协议仍 `active`；6c 连续 3 次错码 → 终止且协议仍 `active`；6d 高危话术 → `BLOCK` 终止。
7. `sub_eval_07_insufficient_data`（T15/E12）：流水覆盖不足 3 个月时 `suspected_scan_status == "insufficient_data"`，签约照常展示，**不报「未发现异常」**。

### 2.2 执行器 `test_subscription_evals.py`
pytest 驱动：用确定性测试替身（假模型/固定 clock）跑 F05/F06/F07/F10 全链路，对工具路由、状态机流转、银行协议最终状态、安全门决策与文案红线做断言；每条用例输出结构化结果。

### 2.3 证据 `evidence/<date>/`
可复跑证据：用例清单、逐条断言结果、涉及的提交 SHA 与运行命令；附一份 `README.md` 说明复跑方式（含后端全量回归命令）。

### 2.4 回归约束
`evals/subscription/` 全绿，且不破坏既有 `evals/transfer`、`evals/security`、`evals/mockbank`、`evals/bills`；后端全量 pytest 通过。

---

## 3. 验收与自检命令

```bash
pytest evals/subscription -q
pytest backend -q      # 后端全量回归
```
- 2026-10-19 实施（评测线，worktree 基于已合入 01–05 的 `9741053`）：`evals/subscription/` 交付 17 条用例 / 349 断言（SF01、SF07、SF02 全链路、SF03 复用、SF04 引导、SF05 消歧拒绝批量、SF06a–d、三条红线专测、首启稳定性、终止任务重复读取、审计模块标签、非 LOW 不降级），另附 `golden_cases.json`（17 条机器可读期望）、`README.md`（覆盖表逐行标注缺口与数量口径）与证据包。
- 运行层次：驱动**平台运行时**（真实 MockBank B29/B30 + 真实 SecurityGate/Executor/审计/存储 + 真实 DemoSecurityPolicy），不复用 backend 测试模块；HTTP/前端层由票 06 与前端包覆盖（README 已标注）。
- **首启偶发失败闭环**（票 05 审查那条 ~3/60 观测的实锤）：修复前 `9741053` 取样 150 次首启 **16 次失败（10.7%）**、引用脱敏探针 20000 采样命中 **407（2.04%）**；票 08 修复（`f202e5d`）后同规模 **0 失败 / 0 命中**，并压成常驻回归 `SUB-OBS-01`（连跑 10 次首启要求 0 失败）；证据 `evidence/2026-10-19/{stability-pre-fix.json,stability-post-fix.json,audit-ref-probe.json}`。
- 证据：`evidence/2026-10-19/manifest.json|md` + 原始报告 gzip（17/17 Passed、349/349 断言，revision `654a0e8`）；`dirty_paths` 如实记录了运行时暂存的票 08 修复。Lead 复核：`pytest evals/subscription -q` 17 passed、`stability_sample.py --attempts 40` 40/40 succeeded。
- 数量口径：本票交付票据要求的 SF01–SF07 + 三红线 + 审查补充，**未宣称** `evals/README.md` §四 的「完整验收集」规模（README 已写明）。
- 交付：**PR #155**（含 CI 空白检查修复 `37dc9fc`）。独立审查子代理在合并时仍在运行，结论到后按需以补丁追加（见最终报告）。
