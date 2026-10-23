# 联动拆票建议：先减支，再养老金，最后生日

Status: planning-approved — PM 2026-10-24「认可，按此方案推进」；21 张正式票已发布，尚未实施。

关联：[共享规格](spec.md)、[公共约定方案](contract-proposal.md)、[项目跟踪](../../docs/01-项目跟踪.md)。本页序号保留为讨论时的候选序号，正式完整票号见 §5；已按工作组分别编号、一票一文件。发布本身不代表接包；后续 Erwin 已接受第一个包并完成九票细化，其他包未记录接受，代码实施未开始。

## 1. 六份交付包

| 包 | 负责人 | 要交付的结果 | 当前状态 |
|---|---|---|---|
| [01 公共接缝与模拟银行](packages/01-platform-bank.md) | Erwin | 业务能够受控衔接，生日有真实模拟资金与订单能力 | blocked；Erwin 2026-10-24 已接包，九票已细化，待公共约定及执行指派 |
| [02 安全边界与专项核验](packages/02-security.md) | Ringo | 新资金动作、父子授权和配送隐私符合安全要求 | planned；未代签、未代领 |
| [03 三个生活目标编排](packages/03-cross.md) | 周恩宇 | 三目标的自主规划与确定性办理规则 | planned；未代领 |
| [04 联动页面体验](packages/04-frontend.md) | 梁爽，六水协助 | 一处看方案、确认当前业务、核对总体结果 | planned；未代领 |
| [05 三主线 E2E 与全面验收](packages/05-cross-e2e.md) | 周恩宇 | 路径就绪即实测，最终形成完整证据与遗留 | planned；未运行 |
| [06 银行专项验收](packages/06-bank-eval.md) | Erwin | 冻结、订单、核销、释放和防重的银行事实证据 | planned；未运行 |

PM 已批准 **21 个单目录交付单元**。具体公共约定确认是相关实施开工的前置；票据可先以 planned 发布，各目录负责人接包后仍可提出内部粒度调整。本页不规定内部实现，不要求一次性完成 21 项后才演示。

## 2. 候选单目录交付单元

“依赖”表示该单元真实接入/验收必须具备的前置；在已定契约下可以按仓库规则先写本目录假实现或测试，但不能用它宣称前置已交付。表中只列直接依赖，依赖会沿前序传递。所有代码单元都另需实际接包及实施授权。

| 序号 / 建议标题 | 负责人 / 单一目录 | 直接依赖（候选序号） | 交付与本单元验证 | 核心场景 |
|---|---|---|---|---|
| 1 公共模型落地 | Erwin / `backend/app/contracts/` | C1—C7 所涉公共约定获确认 | 生活目标、计划/子任务、留存、生日银行结果有明确公共输入输出；旧调用含义不变，序列化和拒绝非法结构有证据 | 全部 |
| 2 任务关系与安排记录持久化 | Erwin / `backend/app/storage/` | 1 | 父子关系、采用/占用、受控引用及必要并发接缝持久保存；重启、双任务冲突、用户/轮次隔离可核对；不在存储复制业务算法 | XL-P06、B07、X03—X05 |
| 3 Harness 受控子任务衔接 | Erwin / `backend/app/agent_platform/` | 1、2；父子授权方案安全审阅 | 以正确能力输入启动/等待/恢复原子任务，沿用原安全执行链；计划与操作可追溯，账单来源继承不回归；先用符合契约的入口验证机制 | XL-S01、X02—X08 |
| 4 联动任务与子交互 API | Erwin / `backend/app/api/` | 3 | 通用任务/交互/事件接口呈现父子真实状态；旧交互拒绝、重复提交不重复推进、取消与重登录恢复准确 | XL-S01、X02—X05 |
| 5 减支编排和共用计划骨架 | 周恩宇 / `backend/app/modules/cross/` | 3 | 真实账单/签约候选→用户选择→逐项公开退订→汇总；无签约、多协议、部分失败和未知可解释，不复制订阅流程 | XL-S01—S05、X01—X04 |
| 6 联动主入口及现有业务装配 | Erwin / `backend/app/agent_platform/` | 5 | 自然目标进入 cross，账单/订阅/转账的公开调用具备真实工厂及配置；显式声明与安全上下文正确，原单项业务仍可用 | XL-S01、XL-P01、X01、X07 |
| 7 总方案、子确认和结果页面 | 梁爽 / `frontend/` | 4 | 先提交版式/文案供 PM 走查，再实现父总览、原子确认卡、逐步结果/等待/恢复；采用方案不等于批准全部办理。复用原转账/退订卡片 | XL-S01、XL-P01、X02—X05、X08 |
| 8 减支核心与关键异常 E2E | 周恩宇 / `evals/cross/` | 6、7 | 真实页面/模型/HTTP/模拟银行实跑 XL-S，核对签约变化和副作用次数；报告失败、阻塞和相关 X 分支，缺陷回原目录 | XL-S01—S05、相关 X |
| 9 养老金安排与留存核算 | 周恩宇 / `backend/app/modules/cross/` | 5 | 加入实际入账范围、生活费口径、退订依赖、刷新及逐笔转账；处理部分成功、并发安排和未知，不造留存交易 | XL-P01—P06、X02—X05 |
| 10 养老金核心与关键异常 E2E | 周恩宇 / `evals/cross/` | 9、6、7 | 从自然目标实际完成 2500/1000 转账、保留 1500；核对数据变化、取消、重启、失败及留存不被绕过 | XL-P01—P06、相关 X |
| 11 生日银行数据与原子提交 | Erwin / `backend/app/storage/` | 1 | 冻结、订单、核销关联及操作记录能一致落库，重复提交不重复消费；账本与业务对象同时成功或失败 | XL-B01、B04—B07 |
| 12 生日模拟银行与网关 | Erwin / `backend/app/services/` | 11 | 落地 B10—B13/B20—B22 及 B14 新动作查询，含固定商品/配送条件、种子及隔离故障；网关无有效执行授权零写入 | XL-B01—B07 |
| 13 生日动作与限定收尾安全门 | Ringo / `backend/app/security/` | 1；C6/C7 安全规则确认 | 冻结/下单/核销按声明确认与验证；收尾只释放原冻结未消费部分。测试越权、篡改、过期、未知、必要审计失败；复用现有执行器 | XL-B05—B07、X05—X08 |
| 14 生日编排及预算约束 | 周恩宇 / `backend/app/modules/cross/` | 5、12、13 | 真实候选→采用→冻结→订单→核销→释放，已采用预算与占用检查；记录付款和订单不同结果，失败/取消不重买不退款 | XL-B01—B07 |
| 15 配送资料受控 API | Erwin / `backend/app/api/` | 2、4；C7 隐私规则确认 | 受控录入取得本人本轮引用，业务按授权解析，普通任务响应与聊天只给脱敏信息；错误引用拒绝，原文不进模型或普通日志 | XL-B02、X05、X08 |
| 16 生日工具、权限与演示装配 | Erwin / `backend/app/agent_platform/` | 6、14、15 | 将真实网关、生日工具声明/执行门、配送引用和故障配置装配到既有运行环境，取消后只走限定收尾；原 S/P 入口继续可用 | XL-B01、B05—B06、X07—X08 |
| 17 商品、配送和资金收尾页面 | 梁爽 / `frontend/` | 7、15 | 先确认具体页面，再接商品选择、配送专用输入、各动作确认、订单/付款/释放区别；未知和待处理有清楚入口 | XL-B01—B06、X08 |
| 18 银行事实和防重专项验收 | Erwin / `evals/mockbank/` | 12 | 固定/变价商品、冻结/核销/释放、订单绑定、各动作同号/异参、未知查询与故障后数据一致性有可重复证据 | XL-B01、B03—B07 |
| 19 联动专项安全验证 | Ringo / `evals/security/` | 16、17 | 针对父子越权、旧确认、跨会话/轮次、外部文字注入、配送隐私及限定释放跑实测；AI 执行与 Ringo 真人签核分别记录 | XL-X02—X08、B05—B07 |
| 20 生日核心与关键异常 E2E | 周恩宇 / `evals/cross/` | 16、17 | 真实页面完整预订付款与差额释放；每种未知/失败/停止有银行及订单事实证据，不以接口单测代替页面路径 | XL-B01—B07、相关 X |
| 21 三目标完整覆盖与体验收口 | 周恩宇 / `evals/cross/` | 8、10、18、19、20 | 核心失败先修复，补齐全部 26 条设计及其关键变体，真实自然表达与页面体验走查，汇总证据/限制供 PM 验收；不代签安全、不自行豁免 | 全部 |

所有代码单元的局部验证还须包含相关权限拒绝、异常和恢复行为；表中的 E2E 单元承担贯通证据。前端 200% 缩放/读屏沿版本已有工作线衔接，不另开重复的全局治理票；联动新增页面仍需实际检查其可用性。

## 3. 可以先进行与不能跳过的依赖

1. **先收口公共差异**：C1—C4 决定父子如何接，C6/C7 决定生日如何受控办理；确认前相关实施票不能标成可直接执行。
2. **先走通减支**：1 → 2 → 3 → 4/5 → 6/7 → 8。它验证公共组织机制和现有业务复用；不需要等待生日银行能力。
3. **养老金接在共用骨架上**：9 可以在 5 后准备；10 在真实平台/页面就绪后运行，不人为依赖生日。
4. **生日前置可提前准备**：1 后可分别准备 11 与 13；11 → 12。14、15、16、17 就绪后即跑 20，不等专项总结才发现页面问题。
5. **最后全面验收**：21 汇总全部证据；局部通过、核心 E2E 通过、全面覆盖、真人安全签核、PM 接受分别记录。任一缺口保留，不能靠合并 PR 数量宣布完成。

6 与 16 是装配票：机制或模块先在自有目录交付，最后由平台把真实实现接起来，避免平台依赖业务、业务又依赖平台的循环。18、19、20 可在各自前置就绪后推进；专业安全签核由真实人员执行，并非一张自动化评测票的隐含输出。

## 4. PM 已确认的规划决定

建议采用上面的顺序与粒度：三主线均在 v0.5；先用减支验证共用机制，养老金接续，生日前置提前准备。21 个单元按目录拆分；后续 Erwin 已接第一个包，其他包仍待本人接受。

PM 已确认此顺序、包边界及粒度，授权继续发布规划票。实际接包和实施单独记录；若由 Codex 代行代码实施，需依据后续明确指派，不能从本轮规划授权推断。

## 5. 已发布的正式票据

PM 2026-10-24 已确认顺序、六包及 21 个单元；下面是正式完整票号。21 票尚未实施；后续 Erwin 已接第一个包，其九票按真实前置标为 blocked 并完成细化，其他包仍为 planned。执行说明见[第一个包交接](../v05-cross-platform/handoff.md)。

| 原候选 | 正式票号、标题与链接 |
|---|---|
| 1 | [v05-cross-platform/01：公共模型落地](../v05-cross-platform/issues/01-public-models.md) |
| 2 | [v05-cross-platform/02：任务关系与安排记录持久化](../v05-cross-platform/issues/02-durable-task-relations.md) |
| 3 | [v05-cross-platform/03：Harness 受控子任务衔接](../v05-cross-platform/issues/03-child-task-dispatch.md) |
| 4 | [v05-cross-platform/04：联动任务与子交互 API](../v05-cross-platform/issues/04-parent-child-api.md) |
| 5 | [v05-cross-business/01：减支编排和共用计划骨架](../v05-cross-business/issues/01-expense-reduction.md) |
| 6 | [v05-cross-platform/05：联动主入口及现有业务装配](../v05-cross-platform/issues/05-cross-runtime-wiring.md) |
| 7 | [v05-cross-frontend/01：总方案、子确认和结果页面](../v05-cross-frontend/issues/01-plan-and-child-interactions.md) |
| 8 | [v05-cross-e2e/01：减支核心与关键异常 E2E](../v05-cross-e2e/issues/01-expense-reduction-e2e.md) |
| 9 | [v05-cross-business/02：养老金安排与留存核算](../v05-cross-business/issues/02-monthly-arrangement.md) |
| 10 | [v05-cross-e2e/02：养老金核心与关键异常 E2E](../v05-cross-e2e/issues/02-monthly-arrangement-e2e.md) |
| 11 | [v05-cross-platform/06：生日银行数据与原子提交](../v05-cross-platform/issues/06-bank-order-freeze-storage.md) |
| 12 | [v05-cross-platform/07：生日模拟银行与网关](../v05-cross-platform/issues/07-birthday-bank-services.md) |
| 13 | [v05-cross-security/01：生日动作与限定收尾安全门](../v05-cross-security/issues/01-birthday-execution-gates.md) |
| 14 | [v05-cross-business/03：生日编排及预算约束](../v05-cross-business/issues/03-birthday-orchestration.md) |
| 15 | [v05-cross-platform/08：配送资料受控 API](../v05-cross-platform/issues/08-controlled-delivery-api.md) |
| 16 | [v05-cross-platform/09：生日工具、权限与演示装配](../v05-cross-platform/issues/09-birthday-runtime-wiring.md) |
| 17 | [v05-cross-frontend/02：商品、配送和资金收尾页面](../v05-cross-frontend/issues/02-birthday-ui.md) |
| 18 | [v05-cross-bank-eval/01：银行事实和防重专项验收](../v05-cross-bank-eval/issues/01-birthday-bank-evidence.md) |
| 19 | [v05-cross-security/02：联动专项安全验证](../v05-cross-security/issues/02-cross-security-evidence.md) |
| 20 | [v05-cross-e2e/03：生日核心与关键异常 E2E](../v05-cross-e2e/issues/03-birthday-e2e.md) |
| 21 | [v05-cross-e2e/04：三目标完整覆盖与体验收口](../v05-cross-e2e/issues/04-full-coverage-and-ux.md) |
