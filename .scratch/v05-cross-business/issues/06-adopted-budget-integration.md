# 06：生日个人预算采用、版本与冻结前占用

Ticket ID: v05-cross-business/06

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [个人预算接入规格](../budget-integration-spec.md)

Type: 开发（本轮只完成规格/拆票/设计审查）

Owner: Erwin（v0.5 阶段统一负责）

Directory: `backend/app/modules/cross/`

Status: blocked — 设计可审查；#293 草稿尚未合入、真实 F10 来源证据缺口待平台接缝，中控未授权实施。

Planning assignee: Erwin 授权执行对话 01a17183-271b-7663-9517-f31a994de51d

Planning accepted at: 2026-10-25

Implementation assignee / accepted at: 未领取，待中控后续派发。

Core scenarios: XL-B07；回归 XL-B01/B03/B05/B06、XL-X02—X05，见[共享规格](../../v05-cross-linkage/spec.md)与[测试框架](../budget-integration-tests.md)。

## What to build

用户明确采用自己的个人预算后，生日办理同时遵守个人剩余额度与本次上限；
省略引用、换任务、改版、刷新或并发都不能绕开已采用约束。冻结前先预留，未知保留，
核实消费与账单只计一次，取消后只做原操作核实和限定收尾。

## Blocked by

- [v05-adopted-budget-storage/01：已采用预算持久化与改版](https://github.com/DrErwin/hackerthon-bank-agent/blob/d0ae73ee3f46a21595311dc236e744b241132652/.scratch/v05-adopted-budget-storage/issues/01-adoption-records.md)，
  [PR #293](https://github.com/DrErwin/hackerthon-bank-agent/pull/293)：接口已读，须验证完成并合入。
- [v05-cross-business/05：受控配送与真实事实](05-birthday-delivery-and-structured-facts.md)，
  [PR #288](https://github.com/DrErwin/hackerthon-bank-agent/pull/288)：同目录顺序实施，不能覆盖未合交付。
- [v05-cross-platform/12：未知响应装配与原 claim 观察](https://github.com/DrErwin/hackerthon-bank-agent/blob/18a3f39bf137f26909b2bd1451a76f6958cd1920/.scratch/v05-cross-platform/issues/12-birthday-response-loss-assembly.md)，
  [PR #289](https://github.com/DrErwin/hackerthon-bank-agent/pull/289)：未知核实后才能验证完整释放。
- 新发现的平台输入前置，尚未建票（中控分派）：真实 F10 采用必须有后台可信来源/原交互证明；
  当前用户 `/inputs` 与模型 provide_input 给 cross 的 choice 相同，单凭 option_id/任务版本不能证明真实采用。
  最小输入输出和核验责任见[规格](../budget-integration-spec.md)“真实采用”段。
- 中控在上述就绪后明确续派实施；本票/ready 标签本身不是授权。

## Start when

中控确认开始，依赖的公开能力及实际合入证据齐备，当前原交互/快照来源接缝已核验。
若运行要求已变为多 worker，须先补跨进程原子接缝，不能以本地锁宣称多进程保证。

## Acceptance criteria

- [ ] constraints 保留且纳入完整请求冲突检查；已有预算/日期/账户/引用不丢失或伪造默认值。
- [ ] adopt/modify/decline 经真实 F10 来源、当前交互、当前计划和原 scope/purpose/limit 快照共同核验。
  裸文本、模型代答、仅 task revision、旧交互或改快照不能生成 AdoptedBudget。
- [ ] 稳定采用 attempt 和原存储参数精确重放；同交互不建第二版、旧重放不复活 superseded。
- [ ] 明示引用精确核验；省略引用也查当前主体/轮次候选，并按实际付款账户/时间/用途判断，重叠不挑宽松限额。
- [ ] task 与准确活动 BudgetRef 绑定；改版/跨月/事实不足停止新增承诺，旧版在途占用和原释放不丢。
- [ ] 本次生日上限和个人预算分开；BudgetView.used/remaining 来自准确 scope 的 L01，remaining 不混扣占用。
- [ ] 冻结提交前持久 pending，登记失败零银行写入；同一任务恢复不重复预留，明确未用才撤销。
- [ ] 真实交易编号把已入账 used、账单前已核实消费、未消费占用分开；同交易不双算、不漏算，历史来源不全时暂停。
- [ ] 当前单进程 Demo 下，同 user/round 串行覆盖首次采用发现、刷新/消重/登记及结算交错；仍使用 storage 原子登记。
- [ ] 未知只查原操作；取消/安全停止不新增购买，释放未知或拒绝不提前撤销占用。
- [ ] 模块声明、用法说明和测试随实现更新，保持单目录，双轴子代理审查必须项清零。

## Verification

按[测试框架](../budget-integration-tests.md)验证真实采用链和银行/存储事实。实施后先逐项局部回归，
再验证真实装配与受影响核心路径；本轮不写或运行这些测试，不调用模型/银行。
页面与完整生日评测复用 [v05-cross-e2e/03](../../v05-cross-e2e/issues/03-birthday-e2e.md)，
其个人预算分支还需本票及真实 F10 来源接缝；不重复建 E2E 收口票。

## Delivery record

- 设计：本票、规格、24组测试框架完成；双轴子代理设计审查通过，Spec初轮两项必须项已修并复审；未实施。
  详见[设计审查记录](../budget-design-review.md)。
- 本票代码/测试/真实模型/HTTP/页面 E2E：均未运行。
- 本轮未改 storage/API/platform、安全规则、共享跟踪、completion 或包总状态；未创建 GitHub Issue。
- AI 设计审查不替代 Erwin/Ringo 真人安全批准或 PM 验收。
