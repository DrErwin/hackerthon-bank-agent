# v04-subscription/13-contract-sensitive-alignment: 公共契约与确认验证字段的退订等级措辞同步

Ticket ID: `v04-subscription/13-contract-sensitive-alignment`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§0 口径统一、§9 Further Notes）；口径依据 PRD §五第 1/10 项
Core scenarios: SF02、SF06；契约验收 M20、公共契约 §5.5 / §8、确认验证字段 §「场景 05 解约」
Verification: 文档链接 / 锚点 / 编号 / 表格列数 / 差异空白检查；S02 行不再出现 `MODIFY`；按公共契约 §8.2 记录「为什么改 / 原来→现在 / 影响方 / 旧代码是否可用」；安全侧审查意见（Ringo）或 PM 豁免留痕
Owner: Erwin（契约负责人）
Directory: `docs/contracts/`
Status: pending
Blocked by: None（合并窗口与票 11 / 12 / 安全侧冻结副本联动，见 §4）
Source issue: [Issue #189](https://github.com/DrErwin/hackerthon-bank-agent/issues/189)

---

## 1. 目标

PM 2026-10-20 13:47 裁定 **1A**（Issue #189）：退订是对齐 PRD 的**三级敏感**操作，提交银行前必须有脱敏 `AuthorizationSnapshot`。本票只把**公共契约侧仍是「二级修改 / `OperationLevel.MODIFY`」的旧措辞**同步为已裁定口径，并补上写前快照要求；**不改任何接口形状、字段、枚举或业务需求**。

> 本票是「建议变更点」的正式记录。接手本票前先核对最新 main；docs 改动属纯文档，按 AGENTS 规则可直接提交推送 main（不建 PR、不等 CI），但公共契约 §8.2 要求的变更说明四件事须写进提交信息并回帖 #189 留痕。

## 2. 变更点（只改 `docs/contracts/` 内两处）

1. `docs/contracts/公共契约-2026-09-23.md` §5.5 S02 `subscription.cancel_subscription` 行：
   - 「二级修改（`OperationLevel.MODIFY`）」→「**三级敏感（`OperationLevel.SENSITIVE`）**」；
   - 同句补：提交银行前须持久化脱敏 `AuthorizationSnapshot`（由 `authorization_snapshot_ref` 引用）；快照或开始日志写入失败立即暂停、不得提交银行（§4.5）。
   - `side_effect=true`、`confirmation_policy="per_action"`、确认按钮 + `basic_identity`/`scope=session` 验证码、同会话复用、不启用模拟人脸、高风险 `BLOCK` 终止等**全部保持不变**。
2. 同文档开头的 2026-10-19 变更记录 ④：
   - 注明该「二级修改」口径已被 PM 2026-10-20 1A 裁定升级为三级敏感；
   - 追加 2026-10-20 变更条目：为什么改（PRD §五 + 分级表已是三级，实现/契约旧口径落后）、原来→现在、影响方（安全冻结副本、`backend/app/modules/subscription/`、`evals/subscription/`）、旧代码是否仍可用（接口与字段不变，安全分级与审计要求变化，按依赖顺序同窗口合入）。
3. 同文档 §9 验收表 M20：追加「提交银行前须有写前脱敏授权快照；快照/开始日志写入失败零银行提交」的验收句（不新开编号）。
4. `docs/contracts/确认验证字段-2026-09-24.md`「2026-10-19 场景 05 订阅代扣解约」段：`二级修改（OperationLevel.MODIFY）` → `三级敏感（OperationLevel.SENSITIVE）`，并补写前快照一句；确认单字段、验证方式、文案边界全部不变。

## 3. 不做与边界

- **不改需求本身**：PRD 是要求方，不改 PRD 的需求与验收；不改 `OperationLevel` 枚举、`CapabilityDefinition` 字段或任何代码契约模型。
- **不改代码**：`backend/` 下所有实现（声明改值属票 11，安全冻结属安全侧票，评测属票 12）。
- **不改银行接口字段**：B30 调用形态、幂等、B14 回查与 `SubscriptionCancelReceipt` 不受操作等级影响。
- 另发现 PRD §3.1 S02 表行仍写「二级修改（per_action）」，与 PRD §五冲突；属纯措辞残留、不是需求变更，建议 PRD 负责人在同一次文档直推中同步（不在本票目录，只登记建议）。
- 不把「确认按钮 / 验证码已有」写成「写前快照已有」。

## 4. 流程与合并窗口

- 按[公共契约 §8.1](../../../docs/contracts/公共契约-2026-09-23.md#8-变更管理防拉通机制④)：本变更改变安全分级与审计/暂停语义，属**协同修改**；且「涉及权限、确认、身份验证、审计规则必须由 Ringo 审查」——需安全侧审查意见，PM 代行/豁免须留痕。
- 契约负责人（Erwin）与受影响模块（`subscription` = Erwin；安全冻结 = Ringo）确认影响与切换时点；公共文档先合，模块 / 安全 / 评测按依赖窗口同步。
- 与 [Issue #164](https://github.com/DrErwin/hackerthon-bank-agent/issues/164) 联动：安全目录将持有订阅声明的独立冻结副本，冻结值需与票 11 的 SENSITIVE 一致；**不得**在 main 上留下「模块 SENSITIVE / 安全预期 MODIFY」的拒绝窗口。

## 5. 验收

1. §5.5 S02 行、2026-10-19 记录 ④、确认验证字段解约段均不再出现 `MODIFY` / 「二级修改」；`grep -n "MODIFY" docs/contracts` 仅剩枚举定义等无关行。
2. 变更记录四问齐全，影响方与「旧代码是否仍可用」可读；链接与锚点有效、表格列数一致。
3. 安全侧审查意见（Ringo）或 PM 豁免留痕记录在 #189 回帖 / 提交信息中；不冒充安全签核。
4. 票 11 / 12 与安全侧 Issue 的票号互链，实施完成后 #189 由 PM 决定关单（本票不关）。

## Comments

- 2026-10-20 只读核对（main `d133f37`）：需要同步的位置共 4 处——`公共契约` §5.5 S02 行、同文档 2026-10-19 变更记录 ④、§9 M20、`确认验证字段` 场景 05 解约段；另 PRD §3.1 S02 行残留旧措辞（建议单列，不改需求）。本次交接只登记建议变更点，未直接修改任何 docs 文件。
