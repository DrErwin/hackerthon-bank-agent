# v04-subscription/12-cancel-snapshot-evals: 退订写前授权快照的端到端断言与失败分支

Ticket ID: `v04-subscription/12-cancel-snapshot-evals`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§5.7 评测集、§4 SF02/SF06）
Core scenarios: SF02、SF06；PRD §五第 10 项「写前快照铁律」；用例落点现有 SUB-SEC-01 与新增失败分支
Verification: `pytest evals/subscription -q` 全绿并在最终提交归档证据；`pytest backend -q` 不回归（Windows 两条 20ms 计时抖动属 Issue #166，单跑复核）
Owner: Erwin
Directory: `evals/subscription/`
Status: resolved
Blocked by: [`v04-subscription/11`：退订声明升级为三级敏感](11-cancel-sensitive-declaration.md)（未改 SENSITIVE 前不会产生写前快照）
Source issue: [Issue #189](https://github.com/DrErwin/hackerthon-bank-agent/issues/189)

---

## 1. 目标

把「退订 = 三级敏感」从「声明改值」证明到「可观察的端到端事实」：评测必须能证明**提交银行前已有脱敏授权快照**、**快照/开始日志写入失败零银行提交**、**重复请求不重复解约**，并清掉 README 里「口径不一致」的缺口记录。评测沿用现有真实组装（真实 `MockBankService`、`SecurityGate`、`DeterministicExecutor`、`AuditJournal`、`DemoSecurityPolicy`；唯一替身＝模型入口），不新造第二套夹具。

## 2. 交付物（缺一不可）

1. **SUB-SEC-01 扩断言（不新建语义重复用例）**：一笔成功退订后——
   - 执行阶段 `security.decided` 的 ALLOW 必须带非空 `authorization_snapshot_ref`；
   - 从真实 `AuditJournal` 读出该证据，校验为脱敏 `AuthorizationSnapshot`：`user_id / session_id / demo_round_id / task_id / operation_id / action_revision` 与执行裁决一致，`confirmation.decision == "approved"`，`verifications` 含同会话（`scope="session"`、`methods=["code"]`）记录，`captured_at` 有值；
   - 同一执行的前置参数证据存在（审计日志对敏感执行 ALLOW 的既有强制规则）；
   - 沿用「不把确认/验证已有说成快照已有」的口径：断言必须落在快照对象本身，不能只数事件类型。
2. **新增失败分支用例（三条，编号按 `cases.md` 规则续）**：
   - **快照构造失败**：patch 平台 `AuthorizationSnapshot` 构造，让 `snapshot_writer` 失败，断言：任务**不得 succeeded**、B30 银行操作行数 = 0、协议保持 `active`、审计中可见暂停/不可用语义的裁决；快照失败不能先调银行。
   - **开始日志写入失败**：让 `tool.started`（写动作）持久化失败，断言：B30 银行操作行数 = 0、协议不变、任务不 succeeded。
   - **敏感裁决持久化失败**（第二轮审查补充红例）：让敏感 `allow` 裁决本身落盘失败，断言：零已持久化 execution allow、B30 = 0、协议不变、无写动作开始日志。
   - 先写「可注入性探针」：若现有公开缝无法在真实组装里注入，如实标 Blocked 并写提供方（平台/安全侧），**不伪造断言、不改生产代码绕过**；注入实现不改银行规则与安全策略。
3. **重复请求不重复解约**：沿用并保持现有幂等断言（同一 `operation_id` 银行操作行数 = 1、重复确认/恢复不二次提交），不新增语义重复用例凑数。
4. **README 与机读期望同步**：
   - 删除 `evals/subscription/README.md` §8「退订的写前 AuthorizationSnapshot」缺口行；覆盖表把「审计链路与写前快照」改为已覆盖并指向新断言；
   - `cases.md`、`golden_cases.json` 的期望字段与断言一一对应，不留「文档写了、机读没有」；
   - 如失败注入显示任务终态为 `failed` 而非「暂停」，在 README §8 如实标注「暂停语义待 PM/安全侧裁定」（见 §4），不擅自新增任务状态。
5. **同提交证据**：`evals/subscription/evidence/<日期>/` 原始报告 + `manifest.json/md`，写清被测提交、解释器、用例/断言数、sha256、`dirty_paths`（必须为空）；必要时按既有做法跑 `PYTHONHASHSEED=0/1/42`。

## 3. 边界

- 只改 `evals/subscription/`；不修改 `backend/`、`docs/` 与安全目录。
- 如 E2E 暴露**平台装配缺口**（`backend/app/agent_platform/`，例如快照未写入/未在银行提交前持久化），停止本票扩范围，回 [Issue #189](https://github.com/DrErwin/hackerthon-bank-agent/issues/189) 说明并另开平台票（Erwin 目录）。
- 不把「快照存在」写成「所有敏感动作都已覆盖」；只断言退订这一条真实链路，其余能力由安全侧回归负责。
- 与 [Issue #164](https://github.com/DrErwin/hackerthon-bank-agent/issues/164) 的合并窗口联动：若 #164 接替 PR 先于票 11 合入，订阅退订会被安全门拒绝、评测无法通过；本票以「票 11 已合 + 安全侧 [Issue #191](https://github.com/DrErwin/hackerthon-bank-agent/issues/191) 的冻结副本已改 SENSITIVE」为运行前提，证据中记录实际基线 SHA。

## 4. 待确认口径（不阻塞本票拆立）

`SecurityGate` 在快照/裁决写入失败时返回 `PAUSE`；当前订阅模块把非 ALLOW/BLOCK 的裁决落为 `failed(SECURITY_REJECTED)`，而转账对 `PAUSE` 落 `NEEDS_ATTENTION`（可恢复）。PRD §五第 10 项写「立即暂停」——是否要求**可恢复暂停**（而非仅「不提交银行 + 失败如实」），列为本轮实施时由 PM/安全侧确认的项；本票先以「零银行提交」为硬验收，不擅自改模块任务状态。

## 5. 验收

- `pytest evals/subscription -q` 在最终提交全绿；`pytest backend -q` 无新增失败。
- 新增断言逐条能定位到 `golden_cases.json` 字段与 `cases.md` 行；README / 票据 / 报告三处数字自洽。
- 证据绑定最终提交（`dirty_paths=[]`），不写超出 runner 能力的断言。

## Comments

- 2026-10-20 实施：SUB-SEC-01 增写前快照断言（执行 allow 带 ref、真实 `AuditJournal` 证据、确认/验证/操作绑定/session/参数证据、脱敏、按 `row_id` 先于 `tool.started`）；新增 SUB-SEC-03（快照构造失败）、04（开始日志失败）、05（敏感裁决持久化失败）三条零银行提交用例；README §8 清缺口并如实登记「终止态语义待 PM/安全侧裁定」；51 条在 cases/golden/测试三处一致。
- 2026-10-20 审查修复：第一轮 P1 闭环；第二轮结论 APPROVE（P0=0/P1=0）。随后处理 P2：README 运行前提改为「SUB-SEC-01/03/04 会红、05 与操作等级无关」、补参数证据与快照脱敏断言、静态期望回填 golden、新增 05 持久化失败红例。
- 验证/证据：`pytest evals/subscription -q` 51 passed（`PYTHONHASHSEED=0/1/42` 一致）；backend 定向 188 passed、全量 965 passed；证据 `evidence/2026-10-20/`，被测提交 `e2d799e`，51 用例 1161/1161 断言、`dirty_paths=[]`、7 个评测源文件 blob 全匹配、报告 gz sha256 校验通过。
- 交付：PR #195（squash `09911e4`）。审查为 PM 指派独立子代理（AI 代行、非 Ringo 本人）。
