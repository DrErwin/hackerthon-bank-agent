# v0.5 风险检测装配：待 PM 裁定材料

Status: proposed — 仅调研与选项，未批准、未实施风险政策或检测装配切换。

Owner: Erwin；由中控转交本人裁定。

关联：[Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)、[v04-risk-inputs/02：生产装配接入检测器并移除转账风险夹具依赖](../v04-risk-inputs/issues/02-detector-assembly-and-fixture-removal.md)、[原规格](../v04-risk-inputs/spec.md)、[v04-ringo-security/02：真实风险识别与安全门组合](../v04-ringo-security/issues/02-real-risk-detector.md)。本材料不改变这些票、交付包或版本总状态。

核查日期：2026-10-25（Asia/Taipei）。代码基线：`e9517b8466f4ca408a6173c2be7d87b116efe5a8`。只读 Issue 正文及全部 7 条评论；未向 Issue 发消息，未关闭问题。

## 需要裁定的业务问题

现在已经可以从真实话术发现一部分危险，也可以可靠地让安全门停止付款。但要让普通转账在完全去掉预设等级后继续办理，仍缺“哪些事实必须查清、哪些未知可以保留、保留时是否允许办理”的决定。仅把检测器接上线，不能得到真实低、中、高三档均可用的体验。

建议本轮保留 **A：当前有限文本检查 + 流程对照**，把未去夹具的事实明确披露；若 PM 要求本期交付不依赖夹具的装配，则选 **B：真实检测、未知暂停**，同时接受普通转账不能通过的结果。**C 会改变未知情况下的放行政策，须另行明确决定和安全审查，本轮不执行。**

## 已具备的实现，以及旧记录需要怎样阅读

| 当前事实 | 直接证据与边界 |
|---|---|
| 可信输入接缝已经提供 | [risk_inputs.py](../../backend/app/agent_platform/risk_inputs.py) L173–245：绑定 user/session/demo_round/task/action/operation/revision/参数引用，拒绝越界、失效和过期引用；原请求与同任务补充对话合并后供检测器进程内读取。该接缝不是待开发空接口。 |
| 真实有限检测器已经提供 | [risk_detector.py](../../backend/app/security/risk_detector.py) L21–65：5 类正向文本规则（冒充公检法等机构、保密/催促、共享屏幕、索要凭据、链接）和已存收款人历史；版本 `v04-lexical-risk-1`。规则未命中不证明安全，教育/否定处理存在适用边界。 |
| 正向 HIGH 优先终止已经实现 | [demo_policy.py](../../backend/app/security/demo_policy.py) L329–342：`bank.submit_transfer` 即使覆盖不足，只要已有正向高风险证据就先给 HIGH；其余覆盖不足才暂停。主线合入提交 `34764ba`（[PR #169](https://github.com/DrErwin/hackerthon-bank-agent/pull/169)）；当前策略版本为 `v05-local-demo-cross-1`（L219），不能沿用 Issue 评论中的候选版本。 |
| 当前运行装配已经调用有限文本检查 | [local_demo.py](../../backend/app/agent_platform/local_demo.py) L182–210：先读可信输入，再按参数查 `transfer_fixtures`，交 `demo_text_risk`；没有匹配夹具也调用文本检查。[demo_text_risk.py](../../backend/app/security/demo_text_risk.py) L33–70 内部调用真实检测器，并叠加共享屏幕/远程控制/催促等规则。平台接线提交 `46117d6`（PR #236），安全实现 `f1c1745`（PR #235），后续有限普通句式扩展至版本 `demo-text-risk-4`。不能再笼统声称“运行装配完全没有检测器调用”。 |
| 普通低、中风险流程仍未去夹具 | `demo_text_risk.py` L61–70：只有每一分句均落入有限普通语句范围，才保留已绑定参数的夹具证据；真实收款人事实可覆盖夹具的熟悉/新收款人值。其他文字或缺夹具保持未知。故“演示有真实危险拦截”与“低、中风险已全部真实识别”是两个不同结论。 |
| 缺事实仍保守暂停，保留来源 | [gate.py](../../backend/app/security/gate.py) L549–566 捕获 `RiskFactsUnavailable` 并暂停；[risk_inputs.py](../../backend/app/agent_platform/risk_inputs.py) L348–382 产生不含原文的不透明证据引用。真实检测器测试检查审计规则、证据版本、零银行操作/流水和终止后不可继续。 |

原 [spec §3.1](../v04-risk-inputs/spec.md) 与 [票 02 Comments](../v04-risk-inputs/issues/02-detector-assembly-and-fixture-removal.md) 中“覆盖检查先于分类，高风险也到不了 BLOCK”是早期问题描述，已由 PR #169 解决高风险分支；**低、中风险需要真实完整证据这一缺口仍成立**。本材料不改历史记录，中控可在正式接线获准后补当前说明。

Issue 决策顺序也须保留：PM [决定 A](https://github.com/DrErwin/hackerthon-bank-agent/issues/160#issuecomment-6268987141) 选择演示沿用流程夹具、不采设备；Ringo 后续说明 [正向 HIGH 已实现](https://github.com/DrErwin/hackerthon-bank-agent/issues/160#issuecomment-6269180535)，随后 [撤回当期接线请求并接受延期](https://github.com/DrErwin/hackerthon-bank-agent/issues/160#issuecomment-6269320684)；PM [再次确认属于 v0.5 跟踪](https://github.com/DrErwin/hackerthon-bank-agent/issues/160#issuecomment-6274013208)。这些历史决定未构成本轮改未知放行政策的授权。

## 真实缺口：不只是接一根线，也不只是缺设备

当前安全门包含 14 个信号枚举（[demo_policy.py](../../backend/app/security/demo_policy.py) L22–61）。真实检测器的实际覆盖如下：

| 信号维度 | 已有真实来源 | 仍缺什么 |
|---|---|---|
| 熟悉收款人 / 新收款人（2 项） | B04 核验 + B08 历史，已存且有历史转出为熟悉；已存无历史转出为新 | 读取失败保持 unknown；180 天窗口尚无正式 PM 冻结决定，当前已经影响历史次数及这两项分类。 |
| 冒充、保密/催促、共享屏幕、索要凭据、陌生链接（5 项） | 有限文本正向匹配 | 只有命中的维度被标为 checked；没命中不等于排除风险。语义改写、亲友冒充等不能据这些规则宣布完整覆盖。 |
| 常见金额 / 异常金额（2 项） | 平台已提供历史样本数、最大单笔、按 2 倍计算的 `usual` | 检测器刻意不消费未批准的金额阈值，不能生成这两项已检查结论；无样本仍 unknown。 |
| 常用设备 / 异常设备或对手方（2 项） | 当前无可信设备来源；对手方历史不等于设备/对手方异常检查 | PM 已决定不采设备，不能填熟悉设备或把 unknown 填 checked；也没有这一组合异常信号的完整识别来源。 |
| 表达清楚 / 犹豫或用途不清（2 项） | 当前没有独立真实判定器；普通句式白名单仅决定是否可保留夹具 | 不能把“没命中诈骗词”当作表达清楚、用途明确或无犹豫。 |
| 短时连续改收款账户（1 项） | 当前检测器未产生该信号 | 缺可信变更历史及窗口/次数定义。即使补设备，其他缺口仍在。 |

来源：[risk_detector.py](../../backend/app/security/risk_detector.py) L34–65；[risk_inputs.py](../../backend/app/agent_platform/risk_inputs.py) L247–344。平台默认 `HISTORY_WINDOW=180天`、`AMOUNT_MULTIPLE=2` 在 L37–38；原规格 §3 与安全票仍将其列为 PM 待确认。金额 `usual` 未被真实检测器使用，并不表示 180 天窗口对当前收款人判定没有影响。

在如实保留这些 unknown 的情况下，当前真实检测器不可能为普通请求填满 14 项。因此，把 `local_demo` 回调直接替换为 `detect_transfer_risk` 会得到“有限正向危险终止，其他转账暂停”，不会自然产生低、中风险放行；加几条金额样本或关键词也不能补齐全部检查。既定三档处置仍见[转账 PRD §9.2](../../docs/prd/01-智能转账-PRD-2026-09-23.md#92-风险分级)：高风险终止、中风险双因子、低风险基础验证，银行规则仍归模拟银行。

## 三个最小选项与业务影响

| 选项 | PM 实际批准什么 | 用户体验与证据含义 | 最小后续工作与依赖 |
|---|---|---|---|
| **A 保持当前边界（建议）** | v0.5 继续有限文本危险拦截 + 固定等级流程对照；不宣称去夹具或低、中风险真实识别完成；不采设备 | 已配置参数和有限普通句式可演示确认/验证/付款，正向危险优先终止，未知文字暂停。比赛可展示既有可验证路径，但 #160/票02仍未完成。 | 以现有代码为准补准确披露与评测证据；不需要改风险政策。180 天窗口继续作为演示读取口径，须由 PM 明确接受或另定值；不因此启用金额安全判定。 |
| **B 真实检测替代夹具，接受普通暂停** | 在明确独立环境/模式中只用真实检测器，不以夹具补证据；接受当前普通转账不可通过的范围 | 可以验证“实际危险话术→终止”和“事实不足→暂停”，不能演示真实低、中风险完成付款；两种证据与原流程对照分开。不会给未知增加放行权。 | 获准后沿 `v04-risk-inputs/02` 在 `agent_platform/` 单独实施受控模式与无夹具回退；检测器已有。真实模型/HTTP/页面补验须按批准范围另行执行，不能以检测单测关闭整个 #160。 |
| **C 限定 Demo 的未知处置新政策** | PM 明确列出哪些未知在限定演示范围可不阻断、替代核验是什么，以及哪些缺失仍必须暂停；保留 unknown，不补 checked；正向 HIGH 仍终止 | 才可能在没有设备来源的前提下实现去夹具的普通付款；但这是减少必查条件或为未知增加办理路径，不能说仍沿用原全覆盖放行政策。即使加双因子也不能证明未知风险已排除，低风险是否仍可达须另定。 | 先由安全目录形成具体规则和验收表，再由平台票接线；若要真实金额判定，还须批准历史窗口与阈值。新语义审查通过前不编码；不采设备决定保持，除非 PM 另行明确变更。 |

不提供“unknown 直接记成 checked”作为选项；这会把没有查到的信息伪装成已排除风险。也不建议本轮临时引入新设备采集或新模型，既违反现有不采集决定，又不能独自解决其余覆盖缺口。

## 可直接使用的裁定记录

由中控转给 Erwin；下面字段保持待决，不将建议写成已批准：

- 选择：`待裁定（A / B / C）`。
- 普通转账在未知情况下的目标：`待裁定（保留夹具流程对照 / 真实模式暂停 / 先制定限定范围新政策）`。
- 180 天历史读取窗口：`待确认维持或给出替代值`；它已经影响收款人历史计数。金额 2 倍阈值：`尚不用于真实风险安全结论；若今后启用须另行批准`。
- 设备：`沿用不采集，保持 unknown`；没有新决定不启动采集。
- 接受的证据范围：`待裁定`；代码、单测、真实检测 HTTP、真实模型/页面 E2E、安全专业签核与 PM 接受分别登记。

若选 A，建议正式接受的表述为：“本版提供有限真实文本危险拦截；普通低、中风险路径保留固定等级流程对照，未完成 #160 的去夹具和三档真实验收。”若选 B，则须增加：“去夹具的真实模式遇到普通请求仍会因证据不全暂停，这是本次接受的能力范围。”

## 本轮实际核查证据

只使用现有代码，未改任何风险政策/装配实现/安全样本，未比较模型，真实模型调用 0 次。测试数据库由 pytest 在本 worktree 旁的独立 `risk-research-pytest` 临时目录生成，未访问共享演示数据；未启动常驻 HTTP 端口。

从隔离 worktree 的 `backend/` 执行（解释器复用已安装依赖，测试导入当前 worktree 源码）：

```powershell
& 'D:/hackerthon-bank-agent/backend/.venv/Scripts/python.exe' -m pytest app/security/test_risk_detector.py app/security/test_demo_text_risk.py app/agent_platform/test_risk_inputs.py -q --basetemp=C:/Users/57652/.codex/worktrees/v05-runtime-risk/risk-research-pytest
```

实际结果：**84 passed in 23.92s**。其中 `test_risk_detector.py` 里的实际检测器 + harness/HTTP 测试验证高风险终止、零银行资金副作用、同任务恢复不能继续；普通真实输入保持 `NEEDS_ATTENTION/PAUSE`。`test_risk_inputs.py` 的部分合法成功/高风险对照使用注入检测器，是可信输入接缝与流程证据，不能改记为真实检测算法完整性证明。HTTP 为进程内 FastAPI TestClient，规划器为受控离线提案；未运行真实模型或浏览器页面。

另用现有纯函数作四组对照（历史事实为构造测试输入；`low()` 为显式测试夹具，不是真实低风险来源），得到：

| 构造输入 | 仅真实检测器 + 现有策略 | 当前混合函数 + 显式低风险夹具 |
|---|---|---|
| 普通话术、已存且有历史收款人 | PAUSE，`risk-signal-coverage-required`；checked 只有收款人两项 | LOW，`demo-risk-low` |
| 普通话术、已存无历史收款人 | PAUSE，同上；checked 只有收款人两项 | MEDIUM，`demo-risk-medium`；真实新收款人覆盖夹具熟悉收款人 |
| 要求打开屏幕共享 | HIGH，`transfer-positive-high-risk:screen_sharing` | 同样 HIGH |
| 无法识别用途的文字 | PAUSE，`risk-signal-coverage-required` | 同样 PAUSE |

该对照用于解释选项 A/B 的行为差异，不计作真实银行事实来源、真实模型、页面 E2E、检测覆盖率、真人安全签核或版本接受。独立子代理审查由本执行对话的主代理在交付前统一安排并记录。

复现辅助对应现有测试：[test_risk_detector.py](../../backend/app/security/test_risk_detector.py) 的 `inputs`、`test_actual_detector_and_gate_are_fail_closed_with_independent_bank_facts`；[test_demo_text_risk.py](../../backend/app/security/test_demo_text_risk.py) 的 `low` / `assess`、`test_only_bounded_normal_turns_retain_the_parameter_bound_fixture`、`test_actual_new_payee_overrides_fictional_familiar_payee`、`test_positive_threat_is_high_even_without_all_facts_or_with_low_fixture`、`test_unrecognized_and_help_prose_cannot_authorize_a_transfer`。上方 84 项命令包含这些函数，不需另调模型复现。

## 独立审查记录

2026-10-25：由未参与起草的子代理独立核对仓库规范、原始任务、Issue #160 全部评论及现有代码。规范 PASS、任务 PASS，必须修复 0；本地链接/锚点与围栏通过。建议补四组对照的测试入口，已按上段补充。未改风险政策、未批准 A/B/C、未代签真人安全或 PM 接受；本材料是待裁定输入。
