# P01：显式演示profile接线与完整跟进来源

Status: developed — 本票局部/广回归及API22脚本模型精确组合通过，待独立两轴/CI与真实模型页面验收
Owner: Erwin；Codex按中控分派，非真人最终安全接受
Accepted at: 2026-10-27
Accepted by: Erwin本轮中控分派，用户明确答复“批准这两笔的限定演示范围，继续完成闭环”
Directory: backend/app/agent_platform/
Ticket: [v05-birthday-platform-dependencies/21](issues/21-pension-profile-wiring.md)
Dependencies: 平台19 [PR #346](https://github.com/DrErwin/hackerthon-bank-agent/pull/346)、安全20 [PR #347](https://github.com/DrErwin/hackerthon-bank-agent/pull/347)，均已合入基线ed1596d5
Integration dependency: 本票实际集成发现的API22 [PR #350](https://github.com/DrErwin/hackerthon-bank-agent/pull/350)，现已合入ef8f9220，保留原失败证据后准确复验通过

## Problem Statement / Solution

新真实P01应能在逐笔确认和双因子后完成两笔转账。安全20已提供用户批准的有限演示事实，但默认运行时不能自动开启；旧任务也可能缺历史跟进，不能只凭父原话继承模拟检查。

公开配置LocalDemoConfig.pension_demo_profile仅接受p01-marked-demo-v1或None（默认）。load_config额外只读进程BANK_PENSION_DEMO_PROFILE，显式值经过同一Literal验证；缺flag不变，错误值沿既有LOCAL_DEMO_CONFIG_INVALID脱敏报错。create_local_app和已有本机隔离启动器因此可复用，不写配置文件/全局环境，不回显秘密。

本票不扩TransferFixture或伪装OwnPayee为SavedPayee。旧A2参数匹配先保持；只有显式开启并具有本轮完整捕捉来源才调用已合安全pension_demo_risk。其他参数/文本按安全20或原demo_text_risk(inputs,None)保留危险优先/unknown。

## 已批准的范围

安全20 [精确原话、四项跟进和两笔参数](pension-demo-risk-20.md)是唯一范围：A1 ownA5/250000分、A1 savedA4/100000分。profile只模拟十二维；真实银行两收款人维度独立，真实NEW_PAYEE仍MEDIUM且每笔确认、验证码、模拟人脸，不把模拟写成真实已检查。

## 来源版本

RiskConversation.CAPTURE_VERSION为risk-conversation-uuid-text-1。Harness仅新建根/子任务时在现有snapshot写risk_capture_version；不补旧任务、不建表或迁移。TrustedRiskInputs继续19全部同user/task/round、持久关联/step/plan、冻结参数校验，并新增可选request_capture_version（缺省None）。只有实际来源父任务与当前子任务均为该版本才给当前完整版本；任一缺失/未知仍None。版本纳入风险引用hash。来源字段和标记不是资金授权。

重启沿已存任务保留标记，不凭当前代码版本升级历史事实。仅有父身份、仅新子任务或旧P01原话相同都不能取得模拟覆盖。仍保留19捕捉的父/子普通F10原文（既有脱敏），未知或危险输入不能被过滤。

中控确认的最小保守边界：已标记任务收到普通text而没有原request_id时，只将该任务capture标记置None，保留历史和原业务含义，不生成或猜UUID，不以此文本声称已完整捕捉。元数据CAS后使用真实新TaskRecord/revision继续；以后有UUID也不补回该完整标记。无text的预算专用choice、确认和验证不触发。旧任务无标记也不补写。固定P01公开F10都有UUID、两笔完整参数不需要child普通text，因此此拒绝边界不扩大已批准范围。

旧planner配置摘要保持原模型/地址/演示事实算法，避免显式开关遮住原任务应有的风险暂停；新profile/capture来源随风险证据记录。模型、确认、验证与资金执行规则不改。

## 核心场景 / 测试框架

| 场景 | 验收 |
|---|---|
| P21-1 显式配置与进程flag | 默认None、正确literal仅进程内开启、错误值固定报错、原配置字节不变、create_local_app实际消费 |
| P21-2 新父子完整来源 | Harness真实创建标记，19的父原请求+四项普通F10完整保留，hash含版本，重启保留 |
| P21-3 默认或旧来源 | 默认未开/任一缺capture/异版本继续PAUSE，不能回填旧历史；旧A2行为保持 |
| P21-4 实际P01闭环 | 真API/Harness/安全/MockBank，唯一脚本模型替身；逐笔确认+code/face，250000与100000仅各一次，回执和留存相符 |
| P21-5 否定/未知/危险/异参和恢复 | 危险先BLOCK，未知/异参暂停且零未授权写；重启原task/op查询不重复提交 |

已约定公开测试接缝为load_config/build_runtime的真实组合、实际ASGI API与RiskInputs公开结果；不以替身风险分类替代安全20。脚本模型只代替外部模型结果，不改policy/guard；真实GLM、浏览器截图与真人接受由中控后继完成。

## Out of Scope / Further Notes

只agent_platform和本组21文件，不改security/Cross/API/frontend/私密配置；不运行外部模型、不触共享数据库、不改旧96/B/C证据。不合并PR或代签真人接受。中控维护共享跟踪，独立两轴审查与CI另记。

已核对仓库工作流及已装Skill；to-spec/to-tickets/implement为disable-model-invocation，未声称自动调用slash，按本轮明确规格与票执行，沿用tdd与pr模板。
