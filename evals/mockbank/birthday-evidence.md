# v0.5 生日银行专项证据

Ticket: [v05-cross-bank-eval/01：银行事实和防重专项验收](../../.scratch/v05-cross-bank-eval/issues/01-birthday-bank-evidence.md)。Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../../.scratch/v05-cross-linkage/packages/06-bank-eval.md)。

基线：`e9517b8466f4ca408a6173c2be7d87b116efe5a8`，2026-10-25；前置银行存储/服务 [PR #261](https://github.com/DrErwin/hackerthon-bank-agent/pull/261)、[PR #262](https://github.com/DrErwin/hackerthon-bank-agent/pull/262) 已合入。只增加 `evals/mockbank/` 评测和本工作组记录，无银行实现、公共契约、安全规则改动。

## 实际运行层级

真实 `BankGateway → MockBankService → MockBankStore → SQLite`，不用银行 stub，不调用真实模型。网关采用显式测试授权回调；其正确放行不证明真实安全执行器、确认/验证、取消或父子任务恢复。未启动 HTTP 或浏览器，不占服务端口；每例在 pytest 临时目录独立建库和装载种子。冻结/核销/释放用专用 EVAL_A/EVAL_B 账户（各 200000 分），跨用户用 EVAL_U2；固定银行时钟 `2026-10-25T04:00:00Z`。配送字段为虚构测试输入。

种子重置验证是两次独立建库与装载相同种子，不冒充 B26 管理重置。服务重启则在同一个 SQLite 文件重新创建服务，验证回执、订单、余额及流水未被重播种覆盖。

## 银行金额事实

金额以分断言，下面用元便于核对。B13 冻结结果、B14 原操作结果、B22 订单、B08 消费流水和数据库账本/付款绑定交叉验证。

| 场景 | 冻结 | 订单及实际消费 | 释放 | 余下冻结 | 最终账面/可用 | 消费流水 / 付款绑定 |
|---|---:|---|---:|---:|---:|---|
| MB-B01 | 500 | 花 199 + 蛋糕 268 = 467 | 33 | 0 | 1533 / 1533 | 2 / 2 |
| MB-B02 | 500 | 花 199 | 301 | 0 | 1801 / 1801 | 1 / 1 |

初始账面/可用均 2000；冻结后可用为 1500，无消费流水。订单先以 unpaid 保存，银行核销后变 paid 并关联真实交易编号；冻结和释放均不生成消费或收入。释放前逐一按原编号核实所有已发起付款均为 succeeded；没有未核实在途付款。上述路径重启后结果保持。机器记录的 `bank_facts` 属性见[本轮 JUnit 原始结果](birthday-results.xml)。

## 覆盖与运行

| 用例组 | 实际验证 |
|---|---|
| MB-B01/B02 | 两组金额、真实花/蛋糕分单付款、B08/B13/B14/B22、账本计数、重启 |
| MB-B03（4 动作） | 提交前原编号 not_found、同号同参回放、同号异参冲突、原回执与全库事实不变；释放后/付款后回放仍返回原成功 |
| MB-B04（4 动作） | 银行提交成功后响应丢失，网关 CALL_TIMEOUT；只查原编号得到成功，流水/付款绑定只增加一次；核销核实后才释放 301 |
| MB-B05（4 动作） | SQLite 在最终回执插入时真实 ABORT；余额、版本、冻结、订单、付款、流水及回执全部回滚；B14 not_found，解除故障后原编号恢复 |
| MB-B06（8 项） | 每个写动作跨用户/轮次复用原编号冲突，跨用户/轮次 B14 拒绝，已持久化事实不变 |
| MB-B07（8 项） | 未配置/拒绝授权的全部写动作 ACCESS_DENIED，无回执、业务事实及编号预留 |
| 订单与账户 | 已付款订单不能换号再扣或换另一账户的冻结再扣；错误商户、金额、分类拒绝；改配送地址或动作名称不能复用编号；错用户不能用他人账户、冻结或订单；空账户不能借用另一账户余额；释放完不能再核销/释放 |
| 商品/故障/重建 | 花199/蛋糕268、报价不符 PRICE_CHANGED（真实价返回）、配送时限拒绝、失败订单原编号回放；故障用户隔离且一次生效；两次新库同种子结论一致、旧资源不可见 |

在仓库 `backend/` 目录运行（Python 3.12，已有后端依赖及 pytest）：

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q ../evals/mockbank app/services app/storage --junitxml=../evals/mockbank/birthday-results.xml -o junit_family=legacy
```

2026-10-25 最终合跑：**149 passed, 4 xfailed in 46.34s**，包括生日专项 37 项通过及4项未满足探针、原银行专项14项通过、服务及存储检查。首次合跑149项通过后，独立审查发现跨轮次缺口，新增四项strict xfail，不计入通过。XML保存最后一次逐例结果（同期 XML 为 153 tests / 4 skipped，与文字记录属另一次同计数运行，计数一致、时间略有差异）。

完整后端检查（同日，同基线，`python -m pytest -q`）：**1588 passed in 893.93s**。它不自动发现 `evals/`；新增生日评测由上面的专项命令单独运行。rebase 到 `a1e8889dd05cb11eb6577a0e11e146538aa42287` 仅引入中控文档更新，银行实现未变。

当前 CI 工作流显式只运行旧 `test_mockbank_eval.py`；新增生日文件必须按专项命令运行，不能用 CI 绿推断生日专项已在 CI 执行。

## 2026-10-26 跨轮次对象边界收口

[v05-bank-round-objects/01（storage）](../../.scratch/v05-bank-round-objects/issues/01-object-round-storage.md)（main `819bbfb`）与 02（services，main `b63ec1b`）已合入；四项 strict xfail 已由 [v05-cross-bank-eval/02](../../.scratch/v05-cross-bank-eval/issues/02-round-object-regression.md) 转为正式回归：

- `test_birthday_bank_eval.py` 单文件 → **42 passed**（原 37 + 4 转正 + 1 混合轮次订单用例）；
- `test_birthday_round_attribution.py` → **3 passed**（旧对象改用银行事实观察，不再依赖 D2 网关读）；
- 记录命令 `python -m pytest -q ../evals/mockbank app/services app/storage` → **217 passed, 0 xfailed in 39.27s**，JUnit [evidence/2026-10-26/bank-round-objects.xml](evidence/2026-10-26/bank-round-objects.xml)；
- 旧 CI 评测 `test_mockbank_eval.py` → **14 passed**；平台订单来源/生日装配/安全释放定向 `app/agent_platform/test_birthday_order_scope.py app/agent_platform/test_birthday_runtime_wiring.py app/security/test_birthday_release.py` → **46 passed**。
- 四项断言：跨轮 B13/B22 读取与 B11 核销/B12 释放均 `ACCESS_DENIED`（写入是失败回执，**不接受 `OPERATION_CONFLICT`**），六类银行表除失败回执外不变、零资金移动；同轮正常路径与合法订单只付一次保留。仍不运行真实页面/模型/HTTP E2E，也不由本报告代签 PM/安全接受；2026-10-25 的 149/4 历史结果保留为当时基线，不重写。

## 未覆盖与交回中控

- **B28 真实故障装配缺口**：`v05-cross-platform/09` 及 PR #279 明确保留未装配；`arm_response_loss` 目前是银行实例的单次用户故障接缝。本专项直接配置自己的实例并观察真实网关超时，不证明通过产品管理入口配置。提供目录：`backend/app/agent_platform/`（必要服务接缝由 `backend/app/services/` 提供）。建议先补 B28→当前隔离银行实例、目标用户/轮次的装配，再由包05真实入口验证。
- **跨轮次验收缺口（2026-10-26 已收口）**：2026-10-25 独立 Spec 子代理及本对话用临时真银行复现：同库 U1 从 D1 改到 D2、测试授权放行时，旧冻结/订单可读，换新编号可核销旧订单199或释放旧冻结500；四项探针当时 `--runxfail` 实跑 **4 failed, 37 deselected**，以 strict xfail 保留。2026-10-26 存储/服务修复后四项已转正并通过（见上节），历史失败与[最小复现](../../.scratch/v05-cross-bank-eval/round-boundary-gap.md)保留。仍不证明真实页面/模型/HTTP E2E，也不代签 PM 或 Ringo 接受。
- **在途限制**：响应丢失故障发生在真实提交之后，B14立即能查到终态；未制造“尚未提交且一直 processing”的生日付款。应用不抢先释放及取消后不复活购买属于业务/平台验证；本票仅证明核实后的银行金额一致。
- **证据层级**：单测/银行存储专项已运行；真实模型、HTTP、页面 E2E 未由本票运行；AI审查、CI、Erwin/PM接受、Ringo真人安全签核分别记录，不能互代。

## 审查与交付

独立 Standards 首审：0 项代码必须修复，1 项交付记录需回填；复跑生日37项通过。独立 Spec 首审：银行事实可信，发现上述跨轮次部分覆盖及交付记录待回填；复跑37项通过。已补四项可重复失败探针并如实标 blocked，未越界修公共代码。二轮审查要求缩窄预期失败异常、允许正确拒绝的失败回执，均已修正：仅 `OldRoundObjectAllowed` 会被标为已知缺口，其他断言或服务错误正常失败。最终复审、PR及 CI 状态见本票交付记录。本报告不宣布包06或 v0.5 已验收。

最终两轴复审均 **0项剩余必须修复**；[PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 已提交，由中控决定合入，未自行合并。最终代码rebase到 `9a479ea4414635772fdb723c02b0fc70b76a1a55`，只新增主线前端及中控文档更新，银行实现与本轮验证相同。

CI实查：head `1fb213b` 的 [Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40167839557/job/121092416355) 为failure且job未启动。GitHub报账号付款失败或消费额度需提高；记录为Actions账号环境阻塞，不能记为CI通过，也不是已经运行的测试失败。后续仅回填文档，不改变本地代码证据；中控合入前复核最终head与账号状态。
