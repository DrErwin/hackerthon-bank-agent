# 01：减支编排和共用计划骨架

Ticket ID: v05-cross-business/01

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（v0.5 阶段承接）

Directory: `backend/app/modules/cross/`

Status: delivered — 已合入（PR #269，squash 7609976，2026-10-24）；账单入口类型化输入缺口仍在账单侧，平台 05/09 装配与 E2E 另行。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: 待后续明确指派（本轮只细化规格与票据）

Accepted by: 未记录（具体实施票）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-S01—S05、X01—X04；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

真实账单/签约候选→用户选择→逐项公开退订→汇总；无签约、多协议、部分失败和未知可解释，不复制订阅流程

## Blocked by

- [v05-cross-platform/03：Harness 受控子任务衔接](../../v05-cross-platform/issues/03-child-task-dispatch.md)

## Start when

- 包负责人 Erwin 已于 2026-10-24 明确领取并授权拆票；具体票实施领取另记。本轮不写代码或运行评测。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [ ] 真实账单对比/明细和当前签约给出来源；空结果、数据不足、查询失败分开。
- [ ] 同名商户不自动匹配；同商户多协议须选择；仅疑似流水不能执行退订。
- [ ] 用户逐项选择、确认后调用公开退订；取消前反悔没有提交，部分失败/未知不批量重做。
- [ ] 总回执只计算已经证实的未来少扣，保留周期/生效信息，不宣称退款；候选步骤可随用户只查/只退一项改变。

## 实施交接：减支与共用计划骨架

**输入与输出**：读取公共 CrossStartInput，确定账户、比较期间和本次目标；输出公共 CrossTaskView、步骤/子任务关联及实际交互。使用方是平台装配与前端；业务结果只能来自账单、签约与退订公开返回。

1. AI 可选择查询顺序、追问范围和提出减支候选；程序核对来源、账户、有效签约、用户选择及当前计划版本。账单不足不补零，名称相似不产生可信关联。
2. 先查事实并展示可选择项目；只查结束时零解约，选中项目逐项调用 subscription.cancel_subscription。每个子任务的确认和验证继续由原订阅流程执行，方案采用不替代逐项确认。
3. 在本目录形成三票复用的最小计划骨架：稳定步骤、当前计划版本、真实子任务引用、依赖、等待/取消/恢复及总回执。只抽取三场景实际共有行为；父子持久化和派发使用平台公开能力。
4. 用户回答指向当前真实交互；同一父任务只推进一个需响应或副作用的步骤。保存成功事实，未知查原操作；更新未执行部分时旧交互失效。按 D2 汇总已完成与已停止内容。
5. 交付模块声明、公开入口/工厂的使用说明和本目录验证，供平台 05 注册装配。本票不以平台 05 为实施前置，避免互相等待；真实页面联调须等装配与前端。

**接入缺口 G1**：当前 Harness.dispatch_child 仅允许 StartTransferInput/CrossStartInput；BillSummarizeInput、SubscriptionListInput、SubscriptionCancelInput 会被 INVALID_CAPABILITY_INPUT 拒绝。由 Erwin 在平台 03 后续修正中提供对应能力的合法类型支持及验证。不得把账单/订阅参数伪装成转账输入，也不得在 cross 复制派发逻辑。详见[工作规格：前置核对](../spec.md#4-前置核对与已知缺口)。

**本票验证**：围绕公开入口检查 XL-S01—S05 及 X01—X04/X07/X08 的相关行为；覆盖完整/空/不足/失败数据、同名多协议、选择保留、逐项确认、重复响应、取消、第一项成功第二项未知、恢复后只查原操作、权限拒绝及外部文本注入。用调用次数和真实子任务关联核对，而非只比较回复文案。替身验证与真实公开入口验证分别记录。

**向下游交付**：平台 05 获得可装配入口和声明；本组 02/03 复用计划骨架；前端/E2E 获得等待、部分完成和未知的结构化样例。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：已合入。PR [#269](https://github.com/DrErwin/hackerthon-bank-agent/pull/269)（squash 7609976，2026-10-24；重建自被连带关闭的 #267），CI 绿。
- 本票验证：`app/modules/cross/` tier-1（真实平台接缝：注册表/dispatch_child/resume_child/父子持久化 + 订阅真实入口）与 tier-2（真实运行时组合：真实确认服务/安全门/模拟银行走完一笔优酷退订并出部分完成回执）通过；覆盖 XL-S01—S05、X02/X03/X04 关键分支。账单步骤以契约形状替身（账单入口类型化输入缺口在账单侧，未代改）。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 审查：子代理审查 PASS-with-notes（无 blocker；边界/三条铁律/回执口径逐项通过）。三条 minor（holding 时不出新菜单、unknown 重新归类、账单不可用如实说明）已修复并随 PR #268 合入主线；note 级（拒绝项回执明细、already_cancelled 边缘、疑似扫描覆盖文案）转后续票/装配票。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 5](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（接包细化）：本阶段包 03 转由 Erwin 承担并已领取；沿用原票号、单目录边界及已批准三票粒度，补齐实施交接、当前前置和验证要求。未启动实施。
