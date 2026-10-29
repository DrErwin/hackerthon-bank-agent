# 14：生日付款前核对本任务获准订单来源

Ticket ID: v05-cross-platform/14

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [公共接缝与模拟银行规格](../spec.md)；本票按已冻结的公共契约 §6.9 / 安全附件 §2 补资源核验接线，具体范围如下。

Type: 开发

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/agent_platform/`

Status: merged — [PR #296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296) 已合入 `620746a4`；原本地验证与双轴审查保留，CI 计费未启动，完整页面及真人接受另记。2026-10-29 核对。

Blocked by: [v05-cross-platform/12：生日响应丢失装配与原号核实](12-birthday-response-loss-assembly.md)，[Depends on PR #289](https://github.com/DrErwin/hackerthon-bank-agent/pull/289)。本票在其 head 上独立组合，未将前序写成已合入。

Source evidence: [PR #294：生日跨轮次真实装配归因](https://github.com/DrErwin/hackerthon-bank-agent/pull/294)；该评测提供证据，不是本票运行代码依赖。

Execution assignee: Codex，运行装配遗留线

Accepted by: Erwin 授权 Codex 实施（中控续派）

Accepted at: 2026-10-25

Core scenarios: XL-B01、XL-B05、XL-X03/XL-X07；定义见[共享规格](../../v05-cross-linkage/spec.md)。以下 OS01—OS04 是本票验证标识，不新设业务主线。

Verification: 真实 ports / 确认 / 双因子 / 执行器 / 银行，临时SQLite；只替换模型构建，不发外部模型请求。无权订单在确认前拒绝、确认后来源失效在执行前拒绝；核对账户、冻结、订单、付款、流水与资金操作不变。合法本任务订单、超时原号回查及重启恢复保持可用。局部检查后按影响范围回归，独立两轴子代理审查、修复复验、单独PR回中控，不合并。

## 已授权问题与最小规格

2026-10-25 中控明确授权按现有要求实施。PR294已观察：D2当前任务经真实确认/双因子，可用本任务新冻结支付已知D1旧订单199元；内部capture端口没有核对订单来源。没有证明普通页面/正常HTTP输入可以注入旧order_id，本票不将内部可达写成外部产品利用。

创建前核对最新main票号01—11、本线待合平台12/PR289与13/PR292，14未使用。本worktree基于289 head `18a3f39`；不带平台13、风险调研或其他目录改动。

### 依据与接线

- [公共契约 §6.9](../../../docs/contracts/公共契约-2026-09-23.md#69-平台内部注册与受控引用)：资源使用须核对任务/会话、轮次、用途与获准引用范围，不能只看用户编号；旧轮次普通资源不能继续办理。
- [安全附件 §2](../../../docs/contracts/安全与审计字段-2026-09-24.md)：先检查可信身份与资源归属；无权引用直接拒绝，不能补确认来换权限；提交前重新核对当前参数和权限。
- 平台在既有生日安全门授权回调中补“本任务获准create_order原操作 + B14成功订单回执”的事实核验，按已有ACCESS_DENIED/不可核实语义处理；该门在确认前、执行前及原操作观察时复用。拒绝由原安全门审计，不新增风险策略或银行规则。
- 不以已知order_id、同用户、已确认/已双因子、纯本地计划或从银行get_order可读取为付款授权。无本任务创建claim、B14未证实成功或订单号不符不能新增扣款。
- 合法订单的参数形状、确认/验证要求、操作编号和B14恢复入口保持；不新增银行round字段，不改security/services/storage/contracts/cross/API。

## Acceptance criteria

- [x] OS01：同用户其他任务订单、D1旧订单均被当前任务拒绝；即使当前任务已有自身同商品合法订单，外来订单也不能取得确认，零扣款，安全决定有ACCESS_DENIED证据。
- [x] OS02：本任务准备的下单候选没有获准执行claim，或绑定到别的任务创建操作时，不能用B14可读订单换权限。
- [x] OS03：合法付款已经确认/双因子后，订单来源绑定失效仍在提交前拒绝，银行事实不变；无法核实原操作也不能继续扣款。
- [x] OS04：本任务合法订单正常完成一次付款；响应未知沿原号回查，重启后仍可观察原结果，不重复扣款。原生日正常/停止/无装配/故障回查路径回归。
- [x] 两个独立子代理分别核对规范与原票/规格，必修项0；独立PR回中控。AI审查、CI、真实模型/HTTP/页面E2E与真人接受分别记录。

## Delivery record

- Worktree: `v05-platform14-order-scope`；分支 `codex/v05-platform14-order-scope`。
- 红灯复现：未加来源检查时，两项真实外来订单反例 **2 failed, 6 deselected in 20.74s**，均观察到 REQUIRE_CONFIRMATION，而非预期BLOCK。实际旧订单被支付199元的原始归因保留在PR294，本票没有改原归因测试/期望。
- 实现：平台补范围授权回调；只认当前任务安全执行记录中的ALLOW创建操作，并核对同一operation_id的B14成功create_order回执/订单号。已有确认、验证不能补足来源；来源暂不可核实时沿用安全门DEPENDENCY_UNAVAILABLE暂停。金额/商户/银行轮次字段及风险政策均未改。
- 定向验证：`app/agent_platform/test_birthday_order_scope.py app/agent_platform/test_birthday_runtime_wiring.py`，**13 passed in 58.70s**（8项本票反例/对照 + 5项既有生日装配）。隔离临时数据；真实ports/门/确认/双因子/执行器/银行，外部模型调用0。
- 反例核对六类银行事实（accounts/freezes/orders/order_payments/ledger_entries/bank_operations）均未变化，未新增付款确认；提交前绑定失效同样零副作用。合法付款仅一次19900分，冻结剩余30100分；原编号回查/重启/重复观察无新扣款。
- 独立 Standards 轴 PASS，必须项0、建议0，独立新测试8 passed in 37.98s；独立 Spec/真实性轴 PASS，必须项0、建议0，独立新旧组合13 passed in 64.25s。无文件返修要求，AI结果不是安全负责人本人批准。
- 模拟银行专项回归 `../evals/mockbank/test_mockbank_eval.py`：14 passed in 1.42s，临时数据库，无模型调用。
- 后端全量：本worktree以PR289 head `18a3f39`为基线组合本票，从backend运行 `python -m pytest -q --basetemp=<本worktree专属临时目录>`，**1599 passed in 875.71s**；未拿该组合结果冒充最新main或其他未合PR的全量结果。解释器复用本线既有隔离虚拟环境，cwd及导入源码为本worktree；不访问共享演示数据、不发外部模型请求。
- 差异空白、改动Python编译、项目及本票链接/锚点/围栏检查通过。真实模型/业务HTTP/页面E2E、CI通过及真人接受未完成。平台12/13与业务未知后取消修复仍各走原PR，不在本票混合。
- 交付：[PR #296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296)，base=`codex/v05-platform12-birthday-response-loss`，Draft。前序289合入后须按squash规则只保留本票提交再更新main。代码提交 `4a414ac`；后续仅回填审查/验证证据。未自行合并。
- CI：head `ac31e2e` 的 [Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40171713488/job/121103742255) 结论failure，注解明确账户付款/spending limit使job未启动，无测试执行证据；不代批例外。后续仅文档回填按路径过滤不主动触发/等待新CI。
- 可解锁：评测/联调线在组合289+本票后，复验PR294内部旧订单付款反例应被拒绝。原归因报告/历史失败事实保持，不在本票改evals或声称普通页面注入曾可达；整体跨轮次/B26重置、页面、专业安全及PM接受仍分别验收。

## 2026-10-25 前序合入后的依赖整理

- 核对PR289已squash合入主线：`31e9f2743028e25503ab5894d6af9f72856b1ea8`。以保存的旧基线 `18a3f39` 为边界，只将本票三条提交接到该main；range-diff逐一相同，无语义改动，沿用原双轴审查。差异仅本票及两个agent_platform文件，没有重复带入平台12。
- 整理后代码/证据提交为 `1efa9e9 / 9b8cafb / af6c2f3`；当前组合定向复验13 passed in 40.16s。未新增全量，原1599项保留原组合基线，不冒充此次新全量。
- 更新原PR296到main，不新建PR；本票未获首批合入或计费例外授权，仍交中控审阅、不自行合并。此前“依赖289未合入”的记录保留为历史。
