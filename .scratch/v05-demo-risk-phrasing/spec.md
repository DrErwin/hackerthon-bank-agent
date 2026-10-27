# v0.5 有限演示转账语序修复

Status: in_progress
Owner: Erwin；Codex 按本轮已授权子任务实施
Directory: `backend/app/security/`
Package: [bank-e2e-remediation/packages/01-demo-remediation：Demo 修复](../bank-e2e-remediation/packages/01-demo-remediation.md)
Source issue: [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)

## Problem Statement

原真实页面请求“转账500元给妈妈”已有匹配的演示账户、收款人和金额，仍因有限正常语法只接受“给妈妈转500元”而暂停。原[暂停证据](../frontend-design-system/evidence/all-journeys/backend-safety-pause.json)保留，不覆盖为成功。

## Solution

本轮用户已选择沿用[风险裁定选项 A](../v05-risk-decision/decision.md)：有限真实危险检测加明确标注的演示风险数据。只补同一有限词汇范围内的常见语序；不把未检查事实标成 checked，不移除夹具，不扩大放行政策。

## User Stories / Core scenarios

1. RP01：用户以“转账500元给妈妈”及同类常见语序发起时，在原参数绑定夹具存在的条件下保留原风险分类，仍走既有确认和验证。
2. RP02：用户使用已有礼貌前缀、付款账户及金额写法时，两种语序一致；小数点属于金额，不能误切成独立句子。
3. RP03：危险前缀、危险后缀或独立危险分句仍优先 HIGH；否定、未知叙述或不在有限范围的对象不能继承夹具。
4. RP04：真实新收款人事实继续覆盖熟悉收款人夹具；缺夹具或检测失败仍暂停。

## Implementation Decisions

- 保留按分句完整匹配，只增加“转/转账/汇款 + 金额 + 给/向收款人”语序。礼貌词、账户、收款人集合保持原值。
- 小数点在两侧都是数字时保留在金额中，其余句号仍分句；不接受超出已有两位小数金额语法的文字。
- 真实危险检测先于普通语法，证据版本递增。确认、权限、审计、安全门及平台夹具装配不改。

## Testing Decisions

先通过既有风险分类接缝保存原失败回归，再扩展同接缝的行为测试；覆盖 RP01–RP04、旧正常句式、危险与未知前后缀、否定、新收款人、无夹具及检测异常。最后运行安全目录及受影响的可信输入/演示装配定向回归；此处无真实模型、页面或真人安全验收声明。

## Out of Scope

去夹具、设备采集、新金额阈值、任意中文安全识别、新收款人词表、平台/API/前端/评测目录实现、关闭 #160、比赛资料、真人签核。

## Further Notes

2026-10-27：按中控明确分派领取。已读 to-spec、to-tickets、implement 本机流程文件；三者均声明 disable-model-invocation，未宣称自动调用。使用已明确的单目录票与测试接缝，不重复索取授权。来源基线沿仓库通用 Skill 规定；独立两轴审查由中控安排。项目跟踪共享条目由中控统一更新。
