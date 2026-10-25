# 01：银行事实和防重专项验收

Ticket ID: v05-cross-bank-eval/01

Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../../v05-cross-linkage/packages/06-bank-eval.md)

Spec: [本工作组规格](../spec.md)

Type: 评测

Owner: Erwin

Directory: `evals/mockbank/`

Status: blocked — 评测实现及已通过银行事实可交付；跨轮次旧对象隔离未满足，待中控分派提供方核对/修复，不能收口专项验收。

Accepted by: Erwin（授权执行对话，银行专项）

Accepted at: 2026-10-25

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B01、B03—B07；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

固定/变价商品、冻结/核销/释放、订单绑定、各动作同号/异参、未知查询与故障后数据一致性有可重复证据

## Blocked by

- [v05-cross-platform/07：生日模拟银行与网关](../../v05-cross-platform/issues/07-birthday-bank-services.md)
- 前置07已随 PR #261/#262 合入；新发现[跨轮次旧对象边界缺口](../round-boundary-gap.md)待平台/安全及必要服务/存储提供方核对，不由本票擅定规则或越界修复。

## Start when

- 中控于 2026-10-25 正式委派本票并授权代码实施、银行专项运行及子代理审查。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。

## Acceptance criteria

- [x] 银行事实证明冻结500、消费467、释放33；消费199后全部已发起付款核实为终态，可释放301。
- [ ] 各写动作的重复、异参、未知回查、订单防重扣、跨用户/轮次和存储故障均有可重复记录。
- [x] 固定种子独立建库重置后结论可复现，实际银行结果及账本计数一致；报告标为银行专项，非B26管理重置、非页面 E2E。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

### 2026-10-25 执行细化

- 前置 PR #261/#262 已合入；基线 `e9517b8466f4ca408a6173c2be7d87b116efe5a8`。
- 固定银行时钟、独立 SQLite 临时目录及专用空账本账户；不启动共享服务、不重置共享数据。
- 通过真实 BankGateway → MockBankService → MockBankStore 验证固定商品订单分开付款、500→467→33、199→301；用 B13/B14/B22、账户与账本/付款绑定交叉核对。
- 四类写动作分别验证同号重放、同号异参、未知原编号查询、已提交响应丢失后回查、跨用户/轮次编号拒绝、缺授权零写入。
- 以测试库 SQLite 触发器在最终操作落库时制造真实约束错误，核对余额、冻结、订单、付款绑定、流水与回执整体回滚；该故障不冒充 B28 产品装配。
- 检查订单金额/商户/分类、账户归属、耗尽冻结、独立种子重建与服务重启；实际跨目录缺口记录后交中控，不越界修复。
- 银行专项不能证明页面/HTTP/真实模型/安全门/真人接受，B28 实际装配另行标注。

- 实现：`evals/mockbank/test_birthday_bank_eval.py`；[银行事实和覆盖证据](../../../evals/mockbank/birthday-evidence.md)、[原始JUnit](../../../evals/mockbank/birthday-results.xml)。分支 `codex/v05-cross-bank-eval-01`，代码提交 `15a3480`，独立 worktree（本机）`C:/Users/57652/.codex/worktrees/v05-cross-bank-eval-01/hackerthon-bank-agent`。[PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 已提交并附本对话，交中控排队；未自行合并。
- 本票验证：最终银行/服务/存储合跑 **149 passed, 4 xfailed in 46.34s**（其中生日37通过、4项strict xfail为未满足轮次要求）；`--runxfail -k old_round_objects`实跑4 failed，保留缺口不算通过。完整后端1588 passed in 893.93s。专项及完整后端范围分别记录，不将任何一项当作页面E2E。
- AI独立审查：Standards轴初审要求回填交付记录；Spec轴发现跨轮次覆盖缺口及同一记录问题。已补失败探针、回填事实并保持跨轮次验收blocked；二轮指出预期失败捕获过宽和拒绝回执比较问题，均修正。两位子代理最终复审确认 **0项剩余必须修复**。复审代码 `e50284a` rebase后为 `15a3480`（只引入主线前端/文档更新，银行/评测内容相同）。AI审查通过不替代银行跨轮次验收或真人批准。
- CI：2026-10-25 实查 head `1fb213b` 的 [Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40167839557/job/121092416355) 为 failure，job尚未启动；GitHub原因为近期账号付款失败或消费额度需要提高。属于Actions账号环境阻塞，不是已运行的测试失败；不能写CI绿。新增生日文件不在现工作流显式旧银行文件命令中，不能由将来CI绿推断新增专项已在CI执行。中控合入前复核最终head及账号问题。
- 银行事实可提供给包05作为B13/B14/B22/B08及账本对照；包05真实故障依赖B28装配（平台09已交付时明确残留），完整轮次隔离还依赖新缺口核对/修复。未发起真实模型、HTTP或页面E2E，未签真人安全/PM接受。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 18](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。
