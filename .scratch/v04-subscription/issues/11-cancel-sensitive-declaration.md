# v04-subscription/11-cancel-sensitive-declaration: 退订声明升级为三级敏感（OperationLevel.SENSITIVE）

Ticket ID: `v04-subscription/11-cancel-sensitive-declaration`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§2 SOP-2、§5.3 业务模块声明；口径依据 PRD §五第 1/10 项）
Core scenarios: SF02（正常退订全链路）、SF06（高危阻断与幂等）；PRD [`05-订阅代扣管理`](../../../docs/prd/05-订阅代扣管理-PRD-2026-10-19.md) §五第 1、10 项
Verification:
- 局部：`pytest backend/app/modules/subscription -q`、`pytest backend/app/agent_platform/test_subscription_runtime.py backend/app/api/test_subscription_api.py -q` 全绿（改值不改变既有确认/验证/幂等路径）
- 整条路径：由 [`v04-subscription/12`：退订写前授权快照的端到端断言与失败分支](12-cancel-snapshot-evals.md) 用真实 `SecurityGate`/`DeterministicExecutor`/`AuditJournal` 断言写前快照、失败零银行提交与重复不重复解约
Owner: Erwin
Directory: `backend/app/modules/subscription/`
Status: resolved
Blocked by: None（跨线合并窗口见 §5，不计为本票前置）
Source issue: [Issue #189](https://github.com/DrErwin/hackerthon-bank-agent/issues/189)

---

## 1. 背景与依据

- PM 2026-10-20 13:47 裁定 **方案 1A**（见 [Issue #189](https://github.com/DrErwin/hackerthon-bank-agent/issues/189)）：对齐 PRD，退订升为**三级敏感**并补**写前脱敏 `AuthorizationSnapshot`**；同时保持已定的基础验证码、同会话复用、LOW/HIGH 两档退订处置，**不启用中风险刷脸**。
- 需求依据：[05 订阅 / 代扣管理 PRD](../../../docs/prd/05-订阅代扣管理-PRD-2026-10-19.md) §五第 1 项（三级敏感定性）与第 10 项（写前快照铁律：`allow / tool.started` 提交银行前必须持久化快照，写失败立即暂停）；[分级与状态对照表](../../../docs/pm/分级与状态对照表.md) 也已把「取消订阅」列在三级敏感。
- 现状：公开能力与私有工具的声明都是 `OperationLevel.MODIFY`，而安全门只为 `SENSITIVE` 调用 `snapshot_writer`（`backend/app/security/gate.py:835`），因此现行退订**不产生写前授权快照**。确认按钮、会话验证码、防重复执行仍受真实安全门控制——本条只缺快照层。

## 2. 改动清单（只改本目录）

1. `backend/app/modules/subscription/manifest.py`：公开能力 `subscription.cancel_subscription` 的 `operation_level` 由 `OperationLevel.MODIFY` 改为 `OperationLevel.SENSITIVE`。其余字段（`side_effect=True`、`confirmation_policy="per_action"`、`required_permissions=["subscription.cancel"]`、`timeout_ms`、`retry_policy="none"`、`handler_ref`）**一处不动**。
2. `backend/app/modules/subscription/reads.py`：私有工具 `subscription.bank.cancel_subscription` 的 `operation_level` 同样由 `MODIFY` 改为 `SENSITIVE`，其余字段不动。
3. `subscription.list_subscriptions` 及其三条只读私有工具（`READ`）不改。
4. 不新增模块单测替代端到端：写前快照是「安全门 + 平台装配 + 审计日志」的联合行为，按仓库「E2E 优先」由票 12 用真实组装断言；既有模块/端口测试保持全绿即可。
5. 随票口径同步（**纯文档**，不并入代码 PR）：`spec.md` §5.3 两处声明（第 206、211 行）与 [`packages/01`](../packages/01-subscription-e2e.md) 遗留登记（第 68 行）的 `MODIFY` 措辞改为 `SENSITIVE` + 写前快照，避免票面与实现再次分叉。

## 3. 不做与边界

- **不改 `backend/app/security/`**：安全门已具备 SENSITIVE 语义（`gate.py` 在 SENSITIVE 且 ALLOW 前调用 `snapshot_writer`，失败返回 `PAUSE`/`AUDIT_UNAVAILABLE`，不调工具）；安全侧独立冻结副本的改值、门回归与说明由安全侧自己的票负责（Ringo，见 #189 决议后新建的 GitHub Issue）。
- **不改 `backend/app/agent_platform/`**：`subscription_runtime.py` 已与转账同构装配 `write_snapshot` + `record_decision`，预期只改声明即触发快照；如票 12 的 E2E 暴露真实缺口，另开平台票，不在本票扩范围。
- **不改模拟银行 / 契约模型**：B30 的调用形态、幂等与 B14 回查不因操作等级变化；`OperationLevel` 枚举与字段无新增，公共契约只有文档措辞需同步（票 13）。
- **不改确认 / 验证 / 风险策略**：LOW 仍是「确认按钮 + `basic_identity`、`scope="session"`、同会话可复用、不刷脸」；HIGH 仍 `BLOCK` 终止。
- 不把「确认按钮 / 验证码已有」说成「写前快照已有」；快照证据以真实评测断言为准。

## 4. 验收

1. 两处声明的 `operation_level == OperationLevel.SENSITIVE`，其余字段逐项不变（安全策略按全字段相等比较）。
2. 真实运行时：执行阶段 `security.decided` 的 ALLOW 带非空 `authorization_snapshot_ref`，且审计证据中可读到脱敏 `AuthorizationSnapshot`（approved confirmation、同会话验证记录、`operation_id`/`action_revision` 与裁决一致）——证据由票 12 提供，本票**不自行宣称快照已通过**。
3. 既有 `evals/subscription` 48 条不回归（票 12 同提交跑）。
4. 快照写入失败 / 开始日志写入失败 → **零银行提交**、银行协议不变；重复请求不重复解约（票 12 断言）。
5. `pytest backend -q` 不回归。

## 5. 跨线落地窗口（Issue #164）

- **main 现状**：`backend/app/security/demo_policy.py` 直接 `import` 订阅的两组声明，改模块声明会自动跟随，不存在拒绝窗口。
- **在途风险**：[Issue #164](https://github.com/DrErwin/hackerthon-bank-agent/issues/164) 的接替分支（`fix/security/issue-164-main-20261020`，head `0b8b2ba`）已把订阅 + 转账共 12 条声明在安全目录**独立冻结**。若它在模块改为 SENSITIVE 之后仍以旧的 `MODIFY` 冻结值合入，退订会被安全门拒绝。
- **约定**：本票的模块声明先合入（或与安全侧改值同窗口）；安全冻结副本随之为 `SENSITIVE` 后再合 #164 接替 PR。任何单边先合都必须确认 main 上**不存在**「模块 SENSITIVE / 安全预期 MODIFY」的拒绝窗口。安全侧动作见 [Issue #191](https://github.com/DrErwin/hackerthon-bank-agent/issues/191)（转给 Ringo）。

## Comments

- 2026-10-20 只读核对（交接材料 `handoff-2026-10-20-04-subscription-cancel-snapshot.md`，main `d133f37`）：确认本票只需改两处声明值；`gate.py` / `contracts` 模型 / 审计日志 / 平台装配均已具备 SENSITIVE 写前快照语义，银行侧无授权映射改动。契约、确认验证字段与 PRD §3.1 表行的旧「二级修改」措辞同步列入票 13；口径同步另见 §2 第 5 项。
- 2026-10-20 实施（方案 A）：`manifest.py` 公开能力与 `reads.py` 私有工具 `operation_level` `MODIFY→SENSITIVE`，其余字段逐项不变；模块 `README.md` 公开能力表同步为 `sensitive` 并补写前快照说明（第一轮审查 P1-1）。spec §2/§5.3 三处 + `packages/01` 遗留行纯文档同步（`215edcf`，P1-2）。
- 验证：定向 `app/modules/subscription + app/security + agent_platform/test_subscription_runtime.py + app/api/test_subscription_api.py` 188 passed；全量 backend 965 passed；`evals/subscription` 51 passed（与票 12 合跑）。
- 交付：PR #194（squash `709d844`）；审查为 PM 指派独立子代理两轮双轴（**AI 代行、非 Ringo 本人，不构成安全签核**）。
- 安全侧：订阅声明独立冻结副本改 SENSITIVE 与门回归见 [Issue #191](https://github.com/DrErwin/hackerthon-bank-agent/issues/191)（Ringo）；本票目录未改安全目录。
