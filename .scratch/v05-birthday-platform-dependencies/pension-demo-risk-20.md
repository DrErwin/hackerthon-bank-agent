# P01：明确标注的有限演示风险提供方

Status: in_progress
Owner: Erwin；Codex按中控分派实施，非真人安全接受
Accepted by: Erwin通过本轮中控分派；用户原答复“批准这两笔的限定演示范围，继续完成闭环”
Accepted at: 2026-10-27
Directory: backend/app/security/
Ticket: [v05-birthday-platform-dependencies/20](issues/20-pension-demo-risk-provider.md)

## Problem Statement

真实P01子转账因风险维度覆盖不足暂停。现有A2演示事实不能用于自己的A5或家人A4，子步骤标记也不是用户原话。本票提供已获本轮用户批准的两笔有限演示事实；可信原话来源和显式开启由平台19、21独立交付。

依据：[安全原则](../../docs/principles/02-security-platform.md)、[公共契约](../../docs/contracts/公共契约-2026-09-23.md)、[XL-P PRD](../../docs/prd/06-跨场景联动-PRD-2026-09-23.md)、既有选项A的有限真实检测加明确标注的演示数据。不改变确认、双因子验证、资金执行或银行规则。

## Solution / User Stories

1. 演示者仅在批准的P01原话、跟进和两笔参数上获得标注清楚的模拟风险证据。
2. 用户改收款人、金额、来源或补充未知内容时，继续暂停；不是任意养老金语句识别。
3. 真实危险线索先胜出，真实新收款人不会被模拟常用收款人覆盖。
4. 银行收款人事实缺失时仍缺两维；不得将十二维模拟写成十四维真实已检查。
5. 接入前旧行为保持，旧A2配置与规则保持；实现代码和AI审查不代替真人最终安全验收。

## Implementation Decisions / 公开契约

pension_demo_risk(inputs: RiskInputs) -> DemoRiskEvidence，模块为安全目录的pension_demo_risk，profile/source_version为p01-marked-demo-v1，source明确为marked-pension-demo。

输入只接受可信提供方已经证明的RiskInputs。平台19负责在同user/round范围核验实际任务、source_task_id与持久父子关系、冻结动作与operation/revision/参数引用；原request_id属于父请求，request_source_task_id是已核验父task_id，request_text保留父原话与父子受控普通F10跟进，hash包含来源。不得用模型或请求正文自行构造可信来源。安全函数不重复读库；字段缺失/None/空白或等于当前task_id拒绝模拟覆盖，兼容旧构造时只保留原危险/unknown行为。

第一行逐字等于（不删空白、不规范化、不收尾缀）：

> 这月养老金5000元到账了，帮我安排一下：留1500元生活费，2500元转自己的储蓄账户，1000元给家人，顺便看看没用的扣费。

随后每个换行分隔的完整输入只允许以下四项；中控已确认普通option没有额外text，不需要新增语法：

- 请再列一下可退订项目
- 1500元
- 2500元
- 1000元

未知/空白行、否定、其他解释、改写、外部文字、原话后同句附言与内部子步骤marker均不能继承演示覆盖。历史回放不回填缺失跟进；新实际验收用新的隔离案例。

动作必须为bank.submit_transfer，参数精确限定如下；operation_id仍须与RiskInputs和不可变快照绑定，额外参数不纳入本profile：

| payer_account_id | payee | amount_fen |
|---|---|---:|
| A1 | kind=own, account_id=A5 | 250000 |
| A1 | kind=saved, payee_id=A4 | 100000 |

先运行既有demo_text_risk(inputs, None)，正向HIGH信号先返回，异参/异源也不能跳过危险检查；异常原样交既有门暂停。只有全部匹配才添加模拟signals FAMILIAR_DEVICE、USUAL_AMOUNT_RANGE、CLEAR_REQUEST。模拟checked固定十二维：FAMILIAR_DEVICE、USUAL_AMOUNT_RANGE、CLEAR_REQUEST、UNUSUAL_AMOUNT、RAPID_ACCOUNT_CHANGES、HESITATION_OR_UNCLEAR_PURPOSE、IMPERSONATION、SECRECY_OR_URGENT_PRESSURE、SCREEN_SHARING、CREDENTIAL_REQUEST、UNFAMILIAR_LINK、UNUSUAL_DEVICE_OR_COUNTERPARTY。不因以后增加枚举自动扩大覆盖。

FAMILIAR_PAYEE/NEW_PAYEE两维只来自现有真实detector对银行事实的读取，真实checked/signals覆盖演示。新收款人继续MEDIUM和原双因子路径；未知银行事实仍PAUSE。低风险也仍须原确认与基础验证。evidence_ref只由可信输入引用和profile生成不含原文的摘要；不回显原文、主体或账户。

## Testing Decisions

已约定测试接缝：新公开纯函数及现有DemoSecurityPolicy.assess_risk，不测试私有helper。RiskInputs新增字段尚由平台19提供，局部用明确标注的dataclass测试替身；不将替身当真实来源核验。先一个公开正常场景红绿，再补拒绝和危险分支；最后跑既有文字检测/策略/安全目录回归。

| 场景 | 必须结果 |
|---|---|
| P20-1 两笔精确参数，原话及四种跟进 | 标注演示来源；新收款人MEDIUM，既有收款人LOW；真实两维缺失仍PAUSE |
| P20-2 旧字段/自身来源/空来源；原话、跟进、参数变化 | 与demo_text_risk(inputs,None)同为危险或unknown；不补模拟checked |
| P20-3 危险前后缀/受控父子跟进 | 原正向危险HIGH先胜，无来源/异参也必须拦截 |
| P20-4 调用无状态写入，输入不变，旧A2规则保持 | 证据仅摘要；原风险政策、确认/验证及A2回归通过 |

## Out of Scope / Further Notes

不改platform/api/contracts/私密配置/银行存储，不改A2规则、模型、prompt、旧96/56样例或指标，不运行真实模型。平台19真实来源、21默认None的显式opt-in、后继真实HTTP/页面/银行闭环另票，不自合并或代签真人接受。

本机2026-10-27核对to-spec/to-tickets/implement/code-review已安装，前三项disable-model-invocation，未声称自动调用slash Skill；按已授权规格与单目录票执行，使用tdd与pr模板。来源基线沿仓库固定说明，未安装或升级全局Skill。
