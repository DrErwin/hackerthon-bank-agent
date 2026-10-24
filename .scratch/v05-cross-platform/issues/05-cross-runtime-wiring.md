# 05：联动主入口及现有业务装配

Ticket ID: v05-cross-platform/05

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/agent_platform/`

Status: delivered — 真实组合装配已合入（PR #276，squash 9b421a2，2026-10-24；前置 #269/#268/#275 均已合入）；CI 因账户计费未运行，本地 agent_platform 242 passed 兜底；三主线 E2E 另行记录。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待 Erwin 指派

Accepted by: 未记录（具体票的实施执行者）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01、XL-P01、X01、X07；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

自然目标进入 cross，账单/订阅/转账的公开调用具备真实工厂及配置；显式声明与安全上下文正确，原单项业务仍可用

## Blocked by

- [v05-cross-business/01：减支编排和共用计划骨架](../../v05-cross-business/issues/01-expense-reduction.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 接包；本聊天只细化票据，具体执行者由 Erwin 另行指派并记录领取。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [x] 自然表达三个生活目标时进入已注册 cross；尚未实现目标明确受阻，不伪装成功。（减支/养老金经 planner 公共目录路由到 cross.start_task（#268 后养老金已交付，票面允许演进）；生日明确受阻、零子任务零写入；测试 3 项）
- [x] 真实账单/订阅/转账工厂及上下文在同一运行环境可调用，父子事件可追溯。（真实 local_demo 组合：子任务经真实工厂派生、task_relations 可追溯、订阅盘点真实返回；账单类型化输入缺口在业务侧如实 failed 不伪装——已登记 cross-business 待办）
- [x] 未注册能力、伪造范围或绕过安全门零业务写入；原单业务入口仍能办理。（读阶段 submitted_ledger_count==0；同组合下普通转账走到确认单；授权链经 #275 白名单）

## 实施交接：第一次接上真实联动模块

1. 等待 v05-cross-business/01 的公开入口和模块清单合入，再把 cross 注册到现有能力目录与运行环境。
2. 接账单/订阅/转账真实公开工厂和正确作用域，主入口能从生活目标选择 cross；本票不改其内部业务流程。
3. 当前重点接通减支；养老金和生日若相应业务尚未交付，明确不可办理/待依赖，不伪造成功。养老金后续沿同一公开入口接入，不要求额外复制 Router。

**本票验证步骤**：运行真实装配，用受控外部输入验证目标路由和实际能力选择；原单项业务入口继续工作。记录父子关联与执行门调用；真实模型/页面全链路由 cross E2E 票验收。

**交付物与边界**：现有运行入口的真实注册/配置和针对性装配检查。不得为演示先行使用 hardcode 成功结果或跨目录补 cross。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：已合入。[PR #276](https://github.com/DrErwin/hackerthon-bank-agent/pull/276)，squash 提交 `9b421a2`（2026-10-24）。交付：`local_demo.py` register_cross 装配、`test_cross_runtime_wiring.py`（真实组合 3 项）。
- 本票验证：`app/agent_platform/` 242 passed（新增 3 项，含 test_local_demo 回归）；子代理审查 A—F 全 PASS、无必须修复项（过时注释/恒真断言已修正）。
- 前置补齐：装配核对发现 DemoSecurityPolicy 无 cross.start_task 白名单（跨目录缺口），按 #264 先例开 [v05-cross-security/03](../../v05-cross-security/issues/03-cross-start-policy.md)（PR #275）先行合入。
- CI：账户计费阻塞（组织已知口径），本地全量测试兜底，恢复后 main 推送自动补跑。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 6](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包后细化）：Erwin 明确接受第一个交付包，授权本聊天完成拆票后交其他执行者实施。本票沿用原编号、目录和依赖；具体执行者尚未领取。总交接见[本包交接说明](../handoff.md)。
