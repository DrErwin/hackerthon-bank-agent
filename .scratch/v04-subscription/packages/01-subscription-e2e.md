# v04-subscription/01: 订阅代扣管理端到端闭环（盘点、单笔退订与 30 天到期提醒）

Status: accepted
Owner: Erwin
Accepted by: Erwin
Accepted at: 2026-10-19
Version: v0.4.0
Spec: `.scratch/v04-subscription/spec.md`
PRD: `docs/prd/05-订阅代扣管理-PRD-2026-10-19.md`

---

## 交付包目标

在 v0.4 阶段完成**场景 05：订阅代扣管理（Subscription / Auto-Debit Management）**的纵向端到端交付，覆盖：

1. **SOP-1 代扣与周期性扣费盘点**：支持盘点本行签约代扣协议（`bank_contract`）与流水聚合识别的疑似周期性扣费（`suspected_ledger`），计算月度折算总金额。
2. **SOP-2 单笔本行签约代扣退订**：支持单笔退订消歧、拦截疑似周期扣费并给出外部关闭引导、幂等提示已退订项；对生效中的本行签约代扣执行**前端确认门 + 会话级基础身份短信验证码（`purpose="basic_identity"`，`scope="session"`，无刷脸 `mock_face`）**后调用 `B30 bank.cancel_subscription` 完成解约；高危操控信号（`_HIGH_RISK_SIGNALS`）直接阻断终止；确认与回执文案严格只承诺**“从下一期（YYYY-MM-DD）起不再自动扣费，之前已经扣掉的钱不退”**。
3. **SOP-3 被动式 30 天到期/续费提醒**：在盘点结果中自动标注未来 30 天内即将扣款的生效协议（`is_upcoming_renewal=True`、`upcoming_renewal_count`），并在回复中主动提醒。

---

## 涉及目录与实施票拆分（一票一目录）

按 [AGENTS.md](../../../AGENTS.md) 目录边界要求，本交付包拆分为以下 7 张单目录实施票：

| 实施票标识 | 标题 | 唯一归属目录 | 依赖关系 | 实施票文件 |
|---|---|---|---|---|
| `v04-subscription/01-contract-models` | 订阅代扣公共契约模型与错误源扩展 | `backend/app/contracts/` | 无（底座先行） | [01-contract-models.md](../issues/01-contract-models.md) |
| `v04-subscription/02-mockbank-subscriptions` | 模拟银行 B29/B30 接口、自包含表与种子数据 | `backend/app/services/` | 依赖 `01` | [02-mockbank-subscriptions.md](../issues/02-mockbank-subscriptions.md) |
| `v04-subscription/03-subscription-module` | 订阅代扣业务模块（SOP-1/2/3 与 S01/S02 工具） | `backend/app/modules/subscription/` | 依赖 `01`、`02` | [03-subscription-module.md](../issues/03-subscription-module.md) |
| `v04-subscription/04-security-policy-subscription` | 订阅代扣权限注册与退订风险评估策略 | `backend/app/security/` | 依赖 `01`、`03` | [04-security-policy-subscription.md](../issues/04-security-policy-subscription.md) |
| `v04-subscription/05-platform-subscription-wiring` | 主 Agent 平台注册、意图路由与退订确认验证编排 | `backend/app/agent_platform/` | 依赖 `01`、`02`、`03`、`04` | [05-platform-subscription-wiring.md](../issues/05-platform-subscription-wiring.md) |
| `v04-subscription/06-api-subscription-wiring` | FastAPI 路由泛型放宽、F10 消歧输入与订阅模块接线 | `backend/app/api/` | 依赖 `01`–`05` | [06-api-subscription-wiring.md](../issues/06-api-subscription-wiring.md) |
| `v04-subscription/07-subscription-evals` | 订阅代扣黄金评测集与端到端回归测试 | `evals/subscription/` | 依赖 `01`–`06` | [07-subscription-evals.md](../issues/07-subscription-evals.md) |

---

## 交付与验收记录（2026-10-19）

7 张单目录实施票全部完成并合入 main，另因联调暴露底座缺陷补开票 08：

| 实施票 | PR | 状态 |
|---|---|---|
| 01 契约模型与枚举扩值 | [#146](https://github.com/DrErwin/hackerthon-bank-agent/pull/146) | 已合入（含审查必修修复） |
| 02 模拟银行 B29/B30 与种子 | [#148](https://github.com/DrErwin/hackerthon-bank-agent/pull/148) | 已合入（含审查必修：B30 补偿事务） |
| 03 订阅代扣业务模块 | [#147](https://github.com/DrErwin/hackerthon-bank-agent/pull/147) | 已合入（首轮不通过 → 修 3 项致命 → 复审通过 + 修 P1 重放上报） |
| 04 安全白名单与退订风险策略 | [#150](https://github.com/DrErwin/hackerthon-bank-agent/pull/150) | 已合入（含权限闸门回归补强） |
| 05 平台注册、路由与确认验证编排 | [#152](https://github.com/DrErwin/hackerthon-bank-agent/pull/152) | 已合入（审查通过；审计标签断言补强） |
| 06 API 泛型放宽与 F10 消歧 | [#154](https://github.com/DrErwin/hackerthon-bank-agent/pull/154) | 已合入 |
| 07 黄金评测集与端到端回归 | [#155](https://github.com/DrErwin/hackerthon-bank-agent/pull/155) | 已合入（17 用例 / 349 断言 + 证据包） |
| 08 底座修复：审计脱敏不改写不透明引用 | [#153](https://github.com/DrErwin/hackerthon-bank-agent/pull/153) | 已合入（审查通过、5/5 变异被杀） |
| 09 退订明确拒绝 / 结果未知如实回执 | [#172](https://github.com/DrErwin/hackerthon-bank-agent/pull/172) | 已合入（`c1cdde3`；拒绝如实、超时/未知→`needs_attention`→按原 `operation_id` 回查 B14 不重提；后端 738 passed） |
| 10 完整验收集 | [#175](https://github.com/DrErwin/hackerthon-bank-agent/pull/175) | 已合入（`d6cb6a8`；17→48 条用例、同提交证据 `evals/subscription/evidence/2026-10-20/`） |
| 11 退订声明升级三级敏感（#189） | [#194](https://github.com/DrErwin/hackerthon-bank-agent/pull/194) | 已合入（`709d844`；公开 + 私有声明 `MODIFY→SENSITIVE`，模块 README/spec/包口径同步；定向 188、backend 965 passed） |
| 12 写前快照端到端断言与失败分支（#189） | [#195](https://github.com/DrErwin/hackerthon-bank-agent/pull/195) | 已合入（`09911e4`；51 用例 / 1161 断言、三条失败零提交红例、证据 `evidence/2026-10-20/` 被测提交 `e2d799e`） |

**每票均配独立子代理审查**（AI 审查，非真人专业审查）。票 06/07 的审查在合并后返回「有条件通过」，审查驱动的三项补丁已另开单目录 PR 合入：[#156](https://github.com/DrErwin/hackerthon-bank-agent/pull/156)（确认单账户行「尾号 尾号 0001」用户可见缺陷）、[#157](https://github.com/DrErwin/hackerthon-bank-agent/pull/157)（消歧输入的验证码守卫回归）、[#158](https://github.com/DrErwin/hackerthon-bank-agent/pull/158)（话术红线等值断言 + 稳定性工具自举 + 证据干净树重归档）；票 06/07 的审查子代理在合并时仍在运行，结论到后按需以补丁追加。安全策略票按 PRD 仍需 Ringo 本人审查或 PM 豁免留痕（本次为 AI 独立审查 + 作者修复，**非 Ringo 签署**）。

**已知残留**（详见各票 Comments 与评测 README）：
1. 演示银行里按契约 §5.9 会命中物业/水费/通信等「疑似周期扣费」，疑似区条数不锁死（属正确行为）；
2. 订阅待答确认/验证复用平台既有 `agent_transfer_*` 事实表（表名为历史包袱，语义为平台 task→绑定事实）；
3. 跨动作占用同一 `operation_id` 仍可绑定（需共享作用域表改造）；B30 两段写合一事务需 `storage/` 共享事务入口；
4. 真实 GLM 路由、`reminder_days` / `status_filter` 等入参参数化、两进程并发未覆盖；**完整验收集已由票 10 交付（48 条）**，仍如实 Blocked 的项见 `evals/subscription/README.md`（T17 B26/B27 未实现、E03/E11 话术、E02 第二分支、E04 processing、SOP-3「需要核实」）；**前端订阅插槽不在本包范围**，按 PM 2026-10-20 决定列为 v0.5 第一优先。

## 2026-10-20 票 09 / 10 补充（AI 代填 · 非真人审查）

- **票 09（[#172](https://github.com/DrErwin/hackerthon-bank-agent/pull/172) `c1cdde3`）**：退订「明确拒绝」与「结果未知」如实回执；提交后超时 / 未知转 `needs_attention`，按原 `operation_id` 回查 B14，不重复提交；批量意图被拒后的文字消歧补齐。
- **票 10（[#175](https://github.com/DrErwin/hackerthon-bank-agent/pull/175) `d6cb6a8`）**：完整验收集 17→48 条；同提交证据 `evals/subscription/evidence/2026-10-20/`（48 passed、7 源文件 blob 对 HEAD、`dirty_paths=[]`、`PYTHONHASHSEED=0/1/42` 三次全量一致、独立复核两轴通过）。
- **遗留（不阻塞收口，如实登记）**：[Issue #176](https://github.com/DrErwin/hackerthon-bank-agent/issues/176) 关键内容变化后确认失效路径随进程哈希序非确定（两支均零提交、安全）；**退订声明已于 2026-10-20 按 Issue #189 / PM 1A 裁定升为 `OperationLevel.SENSITIVE` 并补写前 `AuthorizationSnapshot`（票 11），评测断言与证据见票 12**，不再与 PRD §五/§5.10 三级敏感口径冲突；安全侧独立冻结副本改值见 [Issue #191](https://github.com/DrErwin/hackerthon-bank-agent/issues/191)。
- **本期收口口径**：后端闭环 + 完整验收集；真实模型 E2E 与前端订阅插槽留 v0.5。

## 验收标准（Definition of Done）

1. **契约与模拟银行（M19–M21）**：
   - `B29 bank.list_subscriptions` 正确返回 `U1` 的 3 条本行签约代扣（`sub_001` 优酷视频、`sub_002` 云端网盘、`sub_003` 喜马拉雅）与 1 条流水聚合的疑似周期扣费（`sus_oasis_01` 绿洲健身）；
   - `B30 bank.cancel_subscription` 在提供有效 `confirmation_token` 与 `idempotency_key` 时将 `active` 签约项更新为 `cancelled`，写入 `operation_records` 并支持幂等重放与 `B14 get_operation` 查询。
2. **业务 SOP 与话术红线（SF01–SF06）**：
   - SOP-1 + SOP-3 盘点列表按优先级排序，准确计算 `upcoming_renewal_count` 与 `active_total_monthly_equivalent_cents`，附带 30 天续费提醒；
   - SOP-2 严格单笔退订（拒绝一键全退、多候选进 `WAITING_INPUT`）、拦截 `suspected_ledger` 并给出外部引导、对 `cancelled` 项幂等告知；
   - 确认与回执文案只声明**“从下一期（YYYY-MM-DD）起不再自动扣费，之前已经扣掉的钱不退”**，零“会员还能用到哪天”承诺、零“先退再重订”建议。
3. **安全与验证门**：
   - 正常退订走 `WAITING_CONFIRMATION → WAITING_VERIFICATION (basic_identity, session) → COMPLETED`，不拉起 `mock_face`，同一有效会话内第 2 笔退订可复用已通过的 `basic_identity` 验证；
   - 命中 `_HIGH_RISK_SIGNALS` 时直接拦截并置为 `TERMINATED`。
4. **评测回归**：
   - 各票单测与 `evals/subscription/` 黄金评测集全部通过，且不破坏既有 `transfer`、`security`、`mock_bank` 测试。
