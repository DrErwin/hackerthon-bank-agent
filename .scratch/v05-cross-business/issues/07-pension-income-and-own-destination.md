# 07：养老金真实入账识别与本人账户去向

Ticket ID: v05-cross-business/07

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [本票规格](../pension-input-fixes-spec.md)

Type: 开发

Owner: Erwin（授权执行对话代行）

Directory: `backend/app/modules/cross/`

Status: merged — PR #297 已合入 `2a070b9c`；后续获批限定演示 profile 的 P01 新批接口闭环见[实际记录](../../v05-control/http-completed-2026-10-27.md)，原风险暂停批保留。完整页面与最终接受仍待。2026-10-29 核对。

Accepted by: Erwin（授权执行对话代行）

Accepted at: 2026-10-25

Core scenarios: XL-P01/P02/P03，回归 XL-P04—P06、XL-X02—X05。

Blocked by: 本票最终合入由中控核对执行；真实账单装配前置
[PR #284](https://github.com/DrErwin/hackerthon-bank-agent/pull/284) 与
[PR #292](https://github.com/DrErwin/hackerthon-bank-agent/pull/292) 已在第二批合入（4d9bd57 / e402bc4）；本次不重带其补丁。
风险/参数事实由原安全平台线承担，不在本票代填；未知保持暂停。

## What to build

识别合法真实入账；让用户选择真实本人储蓄账户或家人联系人。只走原公开查询和转账入口，
不以余额冒充养老金、不把A5伪造成联系人，不改变风险语义。

## Acceptance criteria

- [x] direction=inflow、nature=transfer 的当前账户流水能被选择；真实交易编号/金额进入来源记录。
- [x] 多笔入账先由用户选定，不自动认全部为养老金；退款/利息/转出/其他账户不混入。
- [x] 本人A5可读可选，即使不在payees；排除付款自身账户，保留家人SavedPayee。
- [x] OwnPayee/SavedPayee及金额通过公开派发传递，不复制转账内部规则，不降低确认/验证要求。
- [x] 查询失败、旧选项、未知、取消及原养老金留存/D1回归不退化；未变风险配置/夹具。
- [x] 契约测试、真实公开能力与284/292组合证据分层记录，两轴子代理必须项清零。

## Verification / Delivery record

按PI01—PI06及现有养老金测试验证，先复现后最小修复；完整E2E仍归
[v05-cross-e2e/02](../../v05-cross-e2e/issues/02-monthly-arrangement-e2e.md)。
已交 [Draft PR #297](https://github.com/DrErwin/hackerthon-bank-agent/pull/297)，未合并。
首次实现后端全量1591 passed（13m38s），审查回修后的最终Cross48 passed；组合52 passed，
MockBank14 passed；Spec独立用例/组合探针各1 passed。双轴复审PASS，原1项P2已修。
CI账户计费导致job未启动，不记为绿；实际转账仍因安全核对未完成暂停、零资金写入。
完整记录见[本票交接](../review-07.md)。未代签真人安全或PM验收。

2026-10-25（中控续派主线整理）：原head `03b2e57` 从基线 `36f1d66` rebase 至
main `0930d6be59c728b9dc0ef4c4ef0b5430da12943e`。README/manifest 两处冲突同时保留
已合入的生日配送/结构化事实与本票养老金入账/本人去向，不重带旧 #288/#289。
本轮 Cross、真实生日装配和未知后停止恢复 **70 passed in 111.71s**；独立 Standards/Spec
均 PASS（必须项/建议均0），Spec 独立复验2项通过。未改风险/参数或上游案例数据，未另跑全量。
仍保持Draft、依赖#284/#292实际合入；#295案例组合由中控续验。不扩大首批CI例外、不宣称E2E。

2026-10-25（第二批最终准备）：Erwin已另行批准第二批298→284→292→295→297及仅本批CI计费本地验证例外。
前四项已合入，原head `9e25a8f` 的五条提交rebase至main `3239fd75417e8f1e47aea0c0db83d734cdfffe6c`，
range-diff五条均为“=”，无冲突/代码变化。Cross与原head及受测五项组合`0aed529`完全一致；
整个backend/evals也与该受测组合一致，沿用70项/Spec独立2项/五项155+1及两轴PASS，不新跑测试。
本票新增仅准备说明；养老金2500/1000仍是方案，首笔安全核对不足暂停、第二笔未派发，不写成已转出。
CI仍按新head实际结果记录于PR正文，计费未启动为Blocked；例外不是CI绿，也不等于本对话获准合并。
