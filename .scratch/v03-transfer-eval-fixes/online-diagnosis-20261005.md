# 2026-10-05 在线未通过项诊断与修复规划

Status: diagnosis-complete / tickets11-12-merged / ticket10-resumed

基线：`1ca061a865a9a83b7454b1d38fc146f3ffed43cb`（本地与远端main核对一致）。原在线153样本143 Passed / 4 Failed / 1 Error / 5 Blocked；同基线离线152 Passed / 1 Blocked。两者不能互相替代。此文记录诊断，未改原报告或版本验收状态。

## 已确认事实

| 样本 | 实际根因 / 当前边界 | 问题记录 |
|---|---|---|
| TF-PAY-11 | reply_only替代明确转账proposal；没有让银行查询联系人。替换为正确proposal后真实链路Passed | [Issue #68](https://github.com/DrErwin/hackerthon-bank-agent/issues/68) |
| TF-INP-08 | 近似金额被分类为普通回复，没有待补金额任务；正确缺项proposal回放Passed | Issue #68 |
| TF-INP-03 | payer_account_id字符串“null”被当成账户，银行precheck返回ACCESS_DENIED/task.failed；改成真正空值即Passed。评测随后点击空interaction引发TypeError | [Issue #70](https://github.com/DrErwin/hackerthon-bank-agent/issues/70)、[Issue #72](https://github.com/DrErwin/hackerthon-bank-agent/issues/72) |
| TF-INP-09 | 用户已收到“需要精确到分／无法处理／请确认”的明确拒绝，评测词汇规则漏判；专用输入仍确定性拒绝 | Issue #72 |
| TF-BNK-01 | 模型正确给出0；StartTransferInput确定性拒绝，但Harness统一转换MODEL_PROPOSAL_FAILED，用户缺金额原因说明 | [Issue #71](https://github.com/DrErwin/hackerthon-bank-agent/issues/71) |
| TF-CNF-10 | 本次两次：Passed、Blocked；第二次propose_transfer后又reply_only，两个结果导致MODEL_PROPOSAL_AMBIGUOUS | [Issue #69](https://github.com/DrErwin/hackerthon-bank-agent/issues/69) |
| TF-CNF-15 | 本次两次：Passed、Blocked；同上。异常发生在初次规划，尚未到取消阶段 | Issue #69 |
| TF-INP-14 | 本次两次均reply_only/task.created失败；原ValueError没有复现，不能追溯为双工具结果 | Issue #68；原异常归因仍未知 |
| TF-RCV-21 | 本次两次：reply_only导致Failed、正确proposal后恢复场景Passed；原ValueError没有复现 | Issue #68；原异常归因仍未知 |
| TF-VFY-16 | Ringo真实攻击来源及专业评测材料缺失，独立依赖，不以自编block替代 | 沿用评测03/04与v0.3票12，无新最终验收票 |

涉及九项原运行全部无bank.submit_transfer调用、账本出流0；本次八次在线复现与五项原输出回放也无新增银行提交。INP03正确空值对照沿完整流程显式确认后有一笔合法提交，单列为正确路径对照，不归入失败样本的Z结论。专业材料项未运行，不能宣称红线或整版已验收。零金额已挡住，不是零金额扣款漏洞；自然语言超过分精度的确定性保证仍不足以从这条正确拒绝证明，不能仅靠改prompt宣称解决所有舍入风险。

## 方法与可复查证据

应用diagnosing-bugs：先用保存proposal回放真实HTTP/Harness/安全门/业务流程/隔离MockBank，稳定重现四Failed及一Error；再逐个改变候选字段/类型比较，最小化判据调用和双工具序列。只在本机忽略目录放诊断脚本，未改产品或评测执行代码。

- 回放命令：依赖环境Python执行 `.mnemon/online-diagnosis-20261005/replay.py`；五项依次 Failed、Error、Failed、Failed、Failed，原TypeError位置完全一致。
- 单变量对照：同目录 `seams.py`；PAY11/INP08正确缺项proposal、INP03只把字符串null改成None后全部Passed。该脚本先再次回放五项；两次回放均红，不是新的在线请求。
- 最小命令：同目录 `minimal.py`；双工具序列无网络复现MODEL_PROPOSAL_AMBIGUOUS；“金额需要精确到分，无法处理。”为False，仅改“必须/不能”即True；零金额契约触发ValidationError。
- 在线命令：同目录 `live_probe.py`；固定INP14/CNF10/CNF15/RCV21各两次，jobs=1、GLM-5.3/Coding Plan、temperature=0/max_retries=0、timeout=60；每样本临时库、不使用配置中的演示库。8次为3 Passed / 3 Failed / 2 Blocked；原153成绩保留不变。`live-probe.json`记录安全工具名/字段及成功状态；未上传原始provider消息、凭据或原JSON。
- 原报告：`.mnemon/online-retest-20261005/full/20261004T161318608992Z/report.json`；离线：`.mnemon/sync-retest-20261004/offline-browser/20261004T152641690100Z/report.json`。目录时间为UTC，本文日期为北京时间。

诊断脚本只在`.mnemon`，不作修复交付。脚本最小化过程中一次可信上下文构造失败（NOT_FOUND），改为实际创建任务后复跑成功；该错误不算产品样本结果。在线异常仅保留工具序列与异常类；本机probe的额外trace未获得错误码，因此以真实双工具序列和独立最小回放确定CNF10/15的新复现根因，不把错误码倒填原报告。

## 最小修复范围与单目录规划

1. [v03-transfer-eval-fixes/10：缺项转账建立任务并诊断模型无有效输出](issues/10-model-transfer-missing-input.md)继续paused，关联Issue #68/#69/#70。建议获实施授权后在agent_platform内明确缺项/未知联系人仍属转账，空值用null或省略，一次有效结果后停止本轮规划。保留冲突结果拒绝；不选择首个/末个结果、不自动重规划、不替用户填写金额。新增PAY11、INP03、CNF10回归覆盖。
2. [v03-transfer-eval-fixes/11：非法金额保留明确拒绝原因](issues/11-invalid-amount-feedback.md)：agent_platform，规划状态proposed，不领取。复用现有错误/回复通道保留金额原因，仍确定性拒绝。真正API契约缺口需另报依赖。
3. [v03-transfer-eval-fixes/12：在线判据与前置交互失败保真](issues/12-live-eval-verdict-fidelity.md)：evals/transfer，proposed，不领取。补精度等义拒绝判据、失败状态不继续输入、保留资金/隐私事实及原异常分类。不降低标准。

三项无实施前置；12修评测判据不依赖模型修好，11金额提示可独立验证；联合真实在线验收需要三项各自能力和Ringo材料。每张开发票一个目录/分支/PR，纯规划未运行CI、未提交/推送文档、未同步飞书。原resolved的01—09不重开；只追加后续问题关联。未更新版本完成状态或恢复模型票实施。

## 未知与后续验证

原INP14/RCV21的ValueError只有异常类，无工具数量、固定安全错误码或解析阶段，无法确定原根因是零结果、多结果或格式/解析。后续应在规划边界保存白名单错误码、结果数量与阶段，不采集原始敏感内容；固定次数复现，仍不得跑到绿。CNF10/15已证明本次同症状双工具原因，但原历史异常的具体工具序列也未保存。

后续实施先针对各票回放和关键反例，再有限真实GLM重复与组合验证；不为本次诊断再跑153。复用既有最高HTTP/任务/银行账本接缝，未引入新的大型评测架构。

### 同样本离线对照核验

九个非专业未通过样本在保存的同主线离线报告中均Passed。PAY11离线给出未知联系人proposal；INP03给出payer_account_id=null而非字符串；INP08/09/14与CNF15/RCV21给出amount_fen=null；CNF10给出40000分/A6；BNK01离线直接给出amount_fen=null，故离线通过不证明proposal=0的错误提示衔接已经验证。INP03离线和正确空值对照按场景确认后成功提交一笔；其余八项离线无提交。这些固定候选只用于区分下游能力与真实模型输出，不替代在线理解成绩。

## 2026-10-05 票11/12实施交付（未合并）

用户明确回复“可以，实施吧”，授权前述票12→11实施；未恢复票10或授权合并。独立交付[PR #73：评测判据与失败交互保真](https://github.com/DrErwin/hackerthon-bank-agent/pull/73)（evals/transfer，HEAD a16efc4）、[PR #74：非正金额明确拒绝及审计](https://github.com/DrErwin/hackerthon-bank-agent/pull/74)（agent_platform，HEAD 401a281）。两轴AI复审无剩余发现，非真人批准。票11/12为implemented、待审查/合入；10仍paused；Issue #68—#72保留开放。没有主线代码修复合入、飞书同步或下一阶段。

23项评测判据回归、6项相关正常场景通过。平台/API137项回归通过；审计补充后48项相关测试通过，两个测试证据字段读取更正后最后3项拒绝/审计故障回归通过。HTTP重复请求保持一次规划/回复，message_completed事件可回放，无资金提交；未直接读取SSE流或新增React页面验收。

最后组合回放原五项在线输出：BNK01、INP09 Passed；PAY11、INP03、INP08继续Failed。原INP03 Error已正确归还业务Failed，保留真实ACCESS_DENIED与共同检查，未修其模型空值。所有原输出回放无银行提交/出流。

限定真实GLM各一次：BNK01 Passed，真实proposal=0由确定性代码拒绝；INP09 Blocked，安全码MODEL_PROPOSAL_AMBIGUOUS。未反复跑到绿，不改原153全量成绩。真实在线发生在审计补充前；其后审计/HTTP及最终组合回放覆盖新分支。模型双结果与缺项问题留票10，专业TF-VFY-16继续依赖Ringo材料，v0.3仍NotAccepted。完整本机实施证据在.mnemon/online-diagnosis-20261005/，未上传原JSON或敏感配置。

最终PR #73/#74代码HEAD的Repository checks均通过；代码未合并，真人安全批准未记录。进度文档单独按纯文档流程发布主线，不运行或等待文档CI。

## 2026-10-05 用户授权AI代审与合并，票10恢复

用户明确要求AI代替Ringo审查并合并PR #73/#74；随后新对话完成票10，Prompt保持简洁统一，测试与审查通过后可以合并。此授权是本次AI代审/合并授权，不记作Ringo本人审查或专业安全验收。

| 实施票 | 合并PR | 合并提交 | 最终代码CI |
|---|---|---|---|
| v03-transfer-eval-fixes/11 | [#74](https://github.com/DrErwin/hackerthon-bank-agent/pull/74) | `2c7ecafd2a94a4ebcd80c651c704f49ca0d98599` | [通过](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37226355691) |
| v03-transfer-eval-fixes/12 | [#73](https://github.com/DrErwin/hackerthon-bank-agent/pull/73) | `ba77dbbf30c01e0244be58c9153807638cb43a6e` | [通过](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37226561639) |

两轴AI与安全代审无剩余发现；PR #73已重新基于合入#74的主线。合并组合23项评测判据通过，主线权限/拒绝/审计6项与最终评测冒烟8项通过。Issue #71/#72按已合入交付关闭；模型Issue #68/#69/#70继续开放。

11/12标为resolved。10由paused恢复ready-for-agent，由新对话领取实施与测试/审查/合并；[票10交接](ticket10-handoff-20261005.md)规定以业务意图、字段确定性、单一结果三条统一原则组织Prompt，具体用例放测试。不得选择首个/末个候选兜底或把普通确认当授权。用户无需再细化技术规划。

真实GLM模型遗留失败与专业TF-VFY-16缺材料依然存在；这些合并不表示模型票10完成或v0.3验收通过。原153在线报告保留，未同步飞书、未进入下一阶段。纯文档进度按主线独立发布，仅内容/链接/编号/空白检查。
