# 01：生日跨轮次边界的真实装配归因

Ticket ID: v05-cross-bank-round-attribution/01

Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../../v05-cross-linkage/packages/06-bank-eval.md)

Spec: [只读归因规格](../spec.md)

Type: 评测

Owner: Erwin

Directory: `evals/mockbank/`

Status: delivered — 只读归因完成，待中控接收及决定最小修复票；不代表原专项验收通过。

Accepted by: Erwin（中控授权执行）

Accepted at: 2026-10-25

Blocked by: None（只读归因不等待公共实现修复；不是原专项验收收口）

Source: [PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 及 2026-10-25 中控续派；保留其blocked与四项已知失败。

Core scenarios: RA01—RA05，见本规格；关联原XL-B及轮次隔离要求。

## 交付及验证

- 独立临时SQLite、真实build_runtime、安全门/执行器、确认/验证、网关与银行；不使用常量允许写回调，不调真实模型。
- 核对旧会话/任务、旧授权、缺claim、当前轮次新任务使用旧对象的不同结果。
- 区分真实ASGI测试请求、直接内部端口探针、静态路径检查和未实现入口；不写页面E2E或实际外部HTTP越权已证实。
- 输出原规则位置、实际调用路径、提供目录及按单目录拆分的最小票建议；不执行修复、不裁定新政策。
- 子代理独立复核后独立PR交中控，不自行合并、不修改共享跟踪/版本完成事实。

## Delivery record

- 基线 `9a479ea4414635772fdb723c02b0fc70b76a1a55`；分支 `codex/v05-bank-round-attribution-02`；独立worktree `C:/Users/57652/.codex/worktrees/v05-bank-round-attribution-02/hackerthon-bank-agent`。
- [归因报告](../../../evals/mockbank/round-attribution.md)及[可执行探针](../../../evals/mockbank/test_birthday_round_attribution.py)，[原始JUnit](../../../evals/mockbank/round-attribution-results.xml)。最终3 passed in 14.28s。
- 旧API身份/任务受阻、真实写claim有效、旧上下文先STALE_ROUND；D2内部端口经过真实确认/验证仍可付款已知D1订单。未证明页面/正常HTTP可注入旧编号；不新增政策，最小平台资源核对票仅建议。
- 原PR290与四项已知失败未改。归因通过不代表原银行专项验收通过。
- 独立Standards/Spec子代理复核均0项必须修复，分别复跑3 passed；轻微模型调用措辞建议已修正。相关原用例4 passed, 32 deselected in 18.50s。
- [PR #294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294) 已提交并附执行对话，交中控排队，未自行合并。代码提交`db66250`；之后仅事实/措辞/交付记录。rebase到`fd6cd703846a9614e32cff1434fdfe343fdd18c8`只引入主线文档及其他评测文档，运行实现未变。
- CI实查head `74e9471` 的[Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40168942779/job/121095667265) failure且job未启动，GitHub原因为账号近期付款失败或消费额度需提高；属于Actions环境阻塞，不记CI绿。中控合入前复核最终head。现CI显式银行命令仍仅旧评测文件，本轮3项由上面的本地命令留证。
- 不以模型替身/ASGI检查冒充真实模型/外部TCP/页面E2E，不重复跑无关全后端/模型评测。只读归因已交；平台最小修复票仍是建议，未代替中控正式分派，未新增银行轮次政策。
