# 06：银行验证侧旧尝试挑战退役接缝

Ticket ID: v05-birthday-platform-dependencies/06
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [G2-B 权威胜序与提供方](../verification-authority.md)
Type: 开发
Owner: Erwin（v0.5 阶段统一负责）
Directory: `backend/app/services/`
Status: implemented — 2026-10-26 实施与两轴回修完成（规格轴 4/5 项复验闭合、第 5 项文档已回写；规范轴必须项已补 README），待合入；未跑真实链路。
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

## Delivery record（2026-10-26 本对话实施）

- 实现：`backend/app/services/mock_bank/verification.py`（银行库新增 `bank_verification_retirements` 表，只加表；
  `retire_action_challenges` 单事务内先按既有规则惰性过期、再判定 passed/failed/expired 拒绝、否则写退役行，
  无挑战也写；`create_verification` 拦截已退役尝试并让任务级终止扫描跳过退役尝试；**五个**迟到入口拒绝——
  `resend_code`/`verify_code`/`start_face`/`verify_face`/`get_demo_code`；只读 `retirement_for` 可回查退役事实）、
  `backend/app/services/bank_gateway/gateway.py`（纯转发）、`backend/app/services/README.md`、
  `backend/app/services/mock_bank/README.md`、`backend/app/services/bank_gateway/README.md`（逐接缝登记）、
  `backend/app/services/test_verification_retirement.py`。
  分支 `codex/v05-birthday-verification-retirement`，提交 `be1c287`（实现）+ `57c755f`（回修）；PR 待审查闭合后提交。
- 定向验证：`app/services` **75 passed**（基线 60 + 新增 **15**）；调用方 `app/security`
  （427）+ `agent_platform/test_session_verification_reuse.py` 合计 **434 passed**；
  CI 同款 `evals/mockbank` **14 passed**。未跑真实跨库联合/E2E/全量 CI。
- **与票面的偏差（已由规格轴审查指出并登记）**：
  1. 票面写「把仍 pending 的挑战标记 `retired`」，但 `challenge_status` 枚举在 `contracts/` 且本票禁止改契约，
     故退役事实落**独立表**、挑战行不删不改（符合「历史保留」AC）；补充只读 `retirement_for(...)` 让调用方可读到退役事实。
  2. 该 operation **尚无任何挑战**时，银行库无法区分「合法新尝试」与「错 task 自报 operation」——这是已知残留风险，
     必须由 02/03 用可信上下文把关，不依赖银行侧认归属。
  3. 被拒退役整笔回滚，事务内的惰性过期不落库（挑战行仍 pending），会在下次读取/扫描按既有规则终态化；
     不是「永远 pending」，已补断言说明。
  4. 实现在事务内先定位该尝试再惰性过期，与票面文字顺序相反但结果等价（审查已确认）。
  5. 两层 `retire_action_challenges` 为 keyword-only；原因码只在后台内部/机器码，不作为 API 用户文案。
- 双轴独立子代理审查（AI，非本人/Ringo 签核）：**规格轴首轮 FAIL**（5 项必须修：退役事实可读+偏差登记、
  `get_demo_code` 守卫、自报 operation 口径登记、拒绝回滚语义补测、票面状态更新）已全部回修，复验 4 项闭合、
  第 5 项为本记录（已回写）；另按审查建议修正 submission 幂等顺序（既有 submission 重放不受退役影响）。
  **规范轴首轮 FAIL**（必须修：两份模块 README 未登记新接缝），已补 `services/`、`mock_bank/` 与 `bank_gateway/` README。
- 未做：真实跨库联合（应用库+银行库）、P09/P10 真实 E2E、02/03 联合、全量后端/CI——按票留给 02/03 与本人。
