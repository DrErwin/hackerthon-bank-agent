# 07：生日模拟银行与网关

Ticket ID: v05-cross-platform/07

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/services/`

Status: delivered — B10—B13/B20—B22 与网关已合入（PR #262，squash fad49e0，含 B08 修复的 storage 侧 PR #261）；B28 演示故障装配归票 09；E2E 另行记录。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待 Erwin 指派

Accepted by: 未记录（具体票的实施执行者）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B01—B07；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

落地 B10—B13/B20—B22 及 B14 新动作查询，含固定商品/配送条件、种子及隔离故障；网关无有效执行授权零写入

## Blocked by

- [v05-cross-platform/06：生日银行数据与原子提交](06-bank-order-freeze-storage.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 接包；本聊天只细化票据，具体执行者由 Erwin 另行指派并记录领取。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [x] B10—B13/B20—B22 实现原契约含义；B14 能查新写动作，统一错误与超时语义。（birthday.py + core.get_operation 动作分发；网关超时/冲突/库错语义）
- [x] 商品价格及可送达性有真实模拟事实；固定花199/蛋糕268等验收种子和隔离故障可复现。（价目 19900/26800、lead 24h/48h、deliver_by 过滤；arm_response_loss 一次性故障）
- [x] 冻结→订单绑定核销→释放对应正确资金状态；冻结/释放不伪造消费或收入。（全链路测试；核销带对手方 consumption 流水、冻结/释放无流水；B08 完整返回）
- [x] 网关默认拒绝缺授权写入；未知先查原编号，不由网关自行换号重试；余额/限额等规则只由银行判定。（authorize_birthday 默认 ACCESS_DENIED 零写入；CALL_TIMEOUT 后 B14 回查 found；全部错误码由银行判定）

## 实施交接：提供可查询、可失败、可恢复的模拟服务

1. 按已有 B10—B13、B20—B22 语义实现冻结、核销、释放、商品和订单；B14 已存在，只扩展对新操作类型的真实查询，不另建第二套编号系统。
2. 通过 BankGateway 提供统一读取/写入入口，写入需要有效执行授权；与安全侧约定窄的授权接缝，真实安全装配在 09 完成。未接入授权时默认拒绝，不能为独立测试绕过网关。
3. 种子覆盖花 199、蛋糕 268 及已确认的配送条件；只做当前 Demo 所需事实，不另建库存/物流平台。
4. 提供可定位到特定操作的隔离故障条件，支撑已执行但响应丢失等关键验收；不把故障配置开放到产品用户流程。

**本票验证步骤**：在服务/网关边界验证冻结500→消费467→释放33，以及消费199后可释放301；核对订单付款、防重、未知回查、超时和无授权零写入。银行专项报告由 mockbank 评测包另跑。

**交付物与边界**：真实银行服务/网关、可重置种子、针对性服务测试与故障使用说明。不得修改 storage/security 的实现来凑本票。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：已合入。[PR #262](https://github.com/DrErwin/hackerthon-bank-agent/pull/262)，squash 提交 `fad49e0`（2026-10-24）；配套 storage 侧 [PR #261](https://github.com/DrErwin/hackerthon-bank-agent/pull/261)。交付：`services/mock_bank/birthday.py`、`core.py` 接入与 B14 分发、`bank_gateway/gateway.py` authorize_birthday 接缝、`test_birthday_bank.py`。
- 本票验证：`app/services/` 59 passed（新增 7 项）；叠加 `app/storage/` 38 passed；CI 通过（PR #261/#262）。
- 审查：首轮子代理审查发现 1 项必须修复（核销流水缺对手方事实污染 B08）——按目录边界拆出 storage PR #261 + 本分支传参闭合；复审 A—D 全 PASS；其余建议项（下单摘要含配送原文、错误语义、去 target detail）已落实。
- 联合 E2E：未因本票发布而通过；银行专项由 mockbank 评测包另行跑；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 12](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包后细化）：Erwin 明确接受第一个交付包，授权本聊天完成拆票后交其他执行者实施。本票沿用原编号、目录和依赖；具体执行者尚未领取。总交接见[本包交接说明](../handoff.md)。
