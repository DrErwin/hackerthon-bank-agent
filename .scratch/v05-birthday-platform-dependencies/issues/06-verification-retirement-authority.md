# 06：银行验证侧旧尝试挑战退役接缝

Ticket ID: v05-birthday-platform-dependencies/06
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [G2-B 权威胜序与提供方](../verification-authority.md)
Type: 开发
Owner: Erwin（v0.5 阶段统一负责）
Directory: `backend/app/services/`
Status: claimed / blocked — 2026-10-26 已登记领取；实施顺序在 01/05 之后、安全 02 之前，尚未开工。
Implementation assignee: Erwin 授权执行对话（本对话，AI 代理）；accepted at 2026-10-26。
领取与顺序见[生日系列执行记录](../../v05-control/birthday-series-2026-10-26.md)。
Blocked by: 本人 2026-10-25 已裁定「完整支持 + 旧验证码例外 G2-B」（[本人裁定](../../v05-control/birthday-owner-decision.md)）；
本票只补提供能力，不改业务语义。安全 02 与平台 03 消费本票；真实联合验证须等三票齐备。

Core scenarios: P09/P10；[P01—P17 验证框架](../spec.md#6-testing-decisions只设计未运行)对应 Cross08 Q03/Q05/Q06。

## 为什么必须有这一票

旧挑战的失败/过期与任务级终止扫描都只存在于银行库
（`backend/app/services/mock_bank/verification.py` `create_verification` 同 task 扫描）；
应用库与银行库没有已证实跨库原子性。要让本人裁定的「已安全撤离的旧挑战不拖停新方案」成立，
必须由**单一权威存储**（银行库）先判先后并把旧挑战退役。安全 02 不得越界改本目录，也不能静默收窄成
「只支持确认态」。

## What to build

1. 银行验证服务新增窄接缝 `retire_action_challenges(context, *, operation_id, action_revision) -> RetirementOutcome`：
   - 在**同一个银行库事务**内先按既有规则 `_expire` 到期挑战，再按 (user/session/round 所属 task, operation_id,
     action_revision) 定位该尝试的 `action_step_up` 挑战；
   - 若存在该尝试 `passed` / `failed` / 已 `expired` 的挑战 → 拒绝（返回明确原因，不写退役）；
   - 否则把该尝试仍 `pending` 的挑战标记 `retired`（保留原行与历史结果，不删除、不改写）；
   - 该尝试**没有任何**挑战时同样成功（确认等待态的正常情形），并写退役记录；
   - 幂等：同参重复调用返回同一退役事实；异参（不同 operation/revision）互不影响。
2. 任务级终止扫描忽略 `retired` 挑战（`failed` 的照旧终止；退役只对本人裁定允许的精确旧尝试生效）。
3. 拒绝对已退役的 (task, operation_id, action_revision) **再创建挑战**，关闭「撤离后迟到准备」窗口；
   对其它尝试、新尝试无影响。
4. 网关暴露该方法（`BankGateway` / 生日 gateway），只做协议隔离，不塞业务判断；不可由模型调用，
   不新增公开 SecurityDecision/任务状态枚举。

## 边界

- 只改 `backend/app/services/`；不改 security/api/agent_platform/contracts/storage/cross。
- 不改既有失败/过期规则、不删挑战、不改写历史结果、不改 #160、不改风险政策。
- 不建立跨库事务或通用两阶段框架。
- 退役不是新购买授权；新方案仍须新确认、必要新验证与新 claim。

## Acceptance criteria

- [ ] 退役与任务级扫描、挑战创建在同一银行库连接/事务语义下判定，不依赖进程内锁，跨进程成立。
- [ ] 撤离先胜：旧挑战退役后，随后超时/失败不再触发同任务 `VerificationTerminated`；旧动作无法再提交。
- [ ] 先失败/先过期/已通过验证：退役拒绝，不写退役事实，编辑不得据此成立。
- [ ] 无挑战（确认等待）与「已发未登记」窗口：无挑战即成功退役；随后迟到创建旧尝试挑战被拒。
- [ ] 幂等与并发：同参重复只一份事实；异参冲突不改变已有记录。
- [ ] 历史保留：挑战行、原结果、时间戳不删不改；退役只增不改。
- [ ] 未授权/跨 task/跨轮次调用拒绝；不接受客户端自报 operation。
- [ ] 生日网关接线；旧转账/订阅/基础身份验证流程与既有测试不退化。
- [ ] 本目录测试只做局部/隔离库验证；真实全链留 02/03 联合与本人 E2E。

## Verification / downstream

实施后以隔离银行库验证：撤离先胜/失败先胜/已通过/无挑战/迟到创建/并发/重放六类；
再与 02/03 组合后验证 P09/P10。真实 E2E 由本人后续安排，本轮不跑。
